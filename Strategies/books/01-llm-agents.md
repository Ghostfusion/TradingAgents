# LLM & Agentic Trading Systems

`book 01/19` · slug `llm-agents` · 134 papers in the corpus · 20 rated high-relevance by the sweep

## 0. Scope

This category covers large-language-model and multi-agent systems applied to equity research, stock/return forecasting, sentiment extraction, disclosure analysis, and autonomous strategy discovery. It is the repo's own subject matter: TradingAgents is a LangChain multi-agent equity-research engine whose governing contract is *compute, don't narrate*, so the corpus's evidence on hallucination, grounding, multi-agent aggregation, evaluation honesty, and look-ahead contamination maps directly onto the codebase's central risk — an LLM claiming something the computed reads did not establish. It matters more than any other category here because the failure modes the papers document (memorization, prompt sensitivity, selection inflation, silent abstention failure) are precisely the ones this repo must already defend against.

## 1. Corpus composition

Counts used: **134** annotated rows in `evidence/llm-agents.md` (high 20 · medium 74 · low 40); the relevance-ranked shortlist carries the full metadata used for the category table.

By year (all 134 annotated rows):

| window | rows |
| --- | --- |
| 2001–2010 | 6 |
| 2011–2020 | 5 |
| 2021–2022 | 3 |
| 2023 | 19 |
| 2024 | 33 |
| 2025 | 35 |
| 2026 | 33 |

By arXiv primary category (top-60 booklist only, since only that subset carries metadata):

| primary | n |
| --- | --- |
| q-fin.ST | 31 |
| cs.CL | 7 |
| cs.LG | 5 |
| q-fin.PM | 4 |
| q-fin.TR / q-fin.RM / q-fin.CP / cs.CE | 2 each |
| stat.ML / q-fin.PR / q-fin.GN / cs.IR / cs.AI | 1 each |

The category is dominated by 2023–2026 work (123 of 134 rows, 92%), almost all of it post-ChatGPT; the pre-2023 tail is agent-based/econophysics simulation that the sweep attached to `orderflow`/`volatility_models` rather than to LLMs. `q-fin.ST` is the modal venue, with a large `cs.CL`/`cs.LG` component. Volumes are exploding: 2026 already matches 2025 despite the corpus snapshot ending early in the year. The medium and low tiers are overwhelmingly sentiment-extraction and "LLM predicts price" papers whose methodology the high tier (and the reviews inside it) largely debunks.

## 2. Deep reads

### 2608.27734v1 — What survives honest evaluation? Leakage-safe, search-aware assessment of LLM-driven trading strategy discovery (2026)
- **Question**: does any LLM-discovered trading strategy survive honest multiple-testing correction plus structural leakage-safety?
- **Data/market**: 453 liquid US large caps (PIT top-200 by trailing 63d dollar volume) plus SPY, design 2017–2021 / held-out 2022–2025; and a 39-ETF multi-asset universe, design 2007–2016 / eval 2017–2025; realistic costs (1bp commission, 2bp spread, square-root impact, 50bp borrow).
- **Method**: the agent composes strategies only through registry-validated tools (look-ahead is *inexpressible*, not discouraged); every evaluation is recorded in a trial ledger; reported performance is deflated by the search's own trial count `N` and Sharpe dispersion `V` (Deflated Sharpe), with PBO via CSCV and stationary-bootstrap CIs.
- **Headline**: deflation does **not** catch leakage — a planted look-ahead oracle posts design SR 34.7 / eval SR 51.5 / DSR 1.00 and passes every statistical test; leakage-safety and search-deflation are complementary. Honest evaluation certifies passive benchmarks (equal-weight B&H DSR 0.97) and rejects **every** LLM-discovered strategy across two frontier models and budgets up to 100 candidates; the "evaporation curve" shows the deflation threshold overtaking the best in-sample Sharpe as trials accumulate. A pre-registered hypothesis (N=1) faces almost no deflation.
- **Limitation**: survivorship in the fixed current-constituent list is disclosed and bounded (it flatters active strategies, so the null is conservative); four-year windows cannot certify moderate edges — nine years barely can.

### 2504.14765v2 — The Memorization Problem: Can We Trust LLMs' Economic Forecasts? (2025)
- **Question**: when an LLM "forecasts" a pre-cutoff outcome, is it reasoning or recalling?
- **Data/market**: US/international macro series, market indices, firm earnings-call transcripts and headlines; GPT-4o, knowledge cutoff Oct 2023.
- **Method**: formal non-identification proof (counterfactual forecasting ability is unrecoverable once the model has seen the realized value) plus a direct elicitation framework (ask for the value given only variable name + date).
- **Headline**: GPT-4o recalls exact S&P 500 levels, unemployment to a tenth of a point, and quarterly GDP growth; instructing it to ignore post-2010 information still yields 97.6% pre-cutoff vs 98.0% post-*artificial*-cutoff threshold accuracy against 40% for genuinely post-cutoff data. Entity-masked earnings transcripts are reconstructed (100% of Apple/Meta/Microsoft calls; company+quarter+year from generic text). Masking, boundary instructions, and fine-tuning-to-forget all provably fail; memorization survives into embeddings. Any evidence of memorization is only a lower bound.
- **Limitation**: the direct-elicitation test is a lower bound; failure to elicit does not prove absence; findings are model- and date-specific.

### 2601.06088v1 — PriceSeer: Evaluating Large Language Models in Real-Time Stock Prediction (2025)
- **Question**: how do frontier LLMs do on live, uncontaminated U.S. stock prediction with internal and external (news/fake-news) information?
- **Data/market**: 110 US stocks, 11 sectors, 249 daily bars each (27,390 points), five technical indicators, top-10 news per stock plus DeepSeek-generated fake news; six LLMs (GPT-5, o3, DeepSeek-R1/V3.2, Claude-Sonnet-4.5, Gemini-2.5-Pro).
- **Method**: live closing-price prediction at 3/5/10-day horizons with relative error and hit-rate; then a $10k allocation task.
- **Headline**: average hit rate just above 0.5 with low relative error at short horizons; performance degrades sharply with horizon (long-term relative errors reach ~5–11% and hit rates fall toward 0.46–0.59). Models are vulnerable to tampered news; sectors differ; top-tier models show only modest potential, and the design cannot isolate *why* a decision was good or bad.
- **Limitation**: one-year data window, no costed portfolio, no data-contamination proof beyond "live and recent"; benchmark is descriptive, not a tradable result.

### 2606.22719v1 — Leakage-Aware Benchmarking of LLM Forecasting (2026)
- **Question**: how much of a retrieval-augmented LLM forecaster's macro factor-ranking signal is the LLM, and how much is the decision-time information set?
- **Data/market**: seven US equity style factors (SMB/HML/RMW/CMA/UMD/BAB/QMJ), 36 monthly walk-forward decisions 2023-04 → 2026-03; lag-shifted FRED macro, Cleveland Fed archived CPI nowcast, FOMC/CPI event summaries.
- **Method**: 7B actor-critic pipeline (Qwen2.5-7B-Instruct, 4-bit, greedy) with ≥12-month embargoed macro-analog retrieval, plus leakage-clean non-LLM baselines (ridge on the same macro/nowcast, kNN macro-analog).
- **Headline**: full pipeline median monthly rank IC +0.154, mean +0.131, but the bootstrap 95% CI includes zero (permutation p=0.11); a plain kNN macro-analog baseline recovers a **comparable median IC** (+0.161). The largest single change is adding the real-time CPI nowcast (replacing the ~10-day-look-ahead BLS print). Only the long-short sanity check (SR +0.71 vs kNN +0.29) favors the LLM.
- **Limitation**: n=36 is underpowered and the authors explicitly refuse to call it a discovery; LLM and kNN are not perfectly information-matched; the allocation is not a deployable claim.

### 2311.15548v1 — Deficiency of Large Language Models in Finance: An Empirical Examination of Hallucination (2023)
- **Question**: how badly do off-the-shelf LLMs hallucinate on concrete financial tasks, and which mitigations work?
- **Data/market**: 192 financial acronyms, 1,215 stock symbols, 160 obscure financial terms, 560 historical stock-price queries; Llama1/2 (7B/13B), GPT-3.5-turbo, GPT-4, FinMA-7B.
- **Method**: four mitigation families — few-shot, DoLa decoding, RAG from Wikipedia, and prompt-based tool learning (emit a call to an Alpha-Vantage wrapper).
- **Headline**: GPT-4 scores 82.5%/90.4% on acronym/symbol recognition and 81.11% FactScore on term explanations; failures are *stale* (returns a delisted symbol as live) and confidently wrong. Llama2-7B stock-price MAE is ~$6,357. GPT-3.5/GPT-4 **abstain** on all tool-requiring stock-price questions without tools — praised as protective. Domain fine-tuning (FinMA-7B) *degrades* general instruction-following (30.4% acronym vs 40.5% base). RAG and tool-calling are the effective mitigations.
- **Limitation**: small task-specific probes; open models are 7B/13B era; the FinMA degradation is one model.

### 2304.07619v6 — Can ChatGPT Forecast Stock Price Movements? (2023/2025)
- **Question**: can GPT score news headlines into return predictions, and what does that reveal about market underreaction?
- **Data/market**: 4,123 US common stocks, major news/newswires, Oct 2021–May 2024 (post-cutoff for the evaluated model).
- **Method**: GPT-4 headline scoring, out-of-sample by construction; long-short daily portfolio; theoretical model of LLM-augmented information processing.
- **Headline**: ~90% hit rate on the *non-tradable* initial reaction; GPT-4 scores significantly predict subsequent drift, strongest for small stocks and negative news; strategy ~34bp/day before costs; forecasting rises with model size; returns decline as LLM adoption rises (price efficiency). High accuracy on the price move does not equal tradable alpha.
- **Limitation**: the headline-accuracy result is largely the contemporaneous reaction; drift is only feasible at market-maker costs; a 2023-era model, and the paper itself predates the memorization problem it later documents.

### 2604.17327v1 — Signal or Noise in Multi-Agent LLM-based Stock Recommendations? (2026)
- **Question**: do a deployed multi-agent LLM system's strong-buy picks beat random same-sized draws, and where does the edge come from?
- **Data/market**: MarketSenseAI (News/Fundamentals/Dynamics/Macro agents → synthesis agent), fixed cohorts: S&P 500 (467 stocks, 19 monthly obs, Sep 2024–Mar 2026) and S&P 100 (94 stocks, 35 obs, May 2023–Mar 2026); signals generated **live**, eliminating look-ahead.
- **Method**: Monte Carlo null (10,000 draws matched on universe/date/count/weighting), NNLS attribution of thesis embeddings onto agent embeddings, date-level IC/ICIR.
- **Headline**: S&P 500 strong-buy EW earns +2.18%/month vs +1.15% passive, p=0.003; S&P 100 +30.5pp compound excess but p=0.17 (not significant). Agent contributions are heterogeneous and rotate with regime (Fundamentals leads S&P 500, Macro S&P 100, Dynamics episodic); no dominant agent. Ordinal-recommendation ICIR +0.489 (p=0.024) on the actionable subset. The system itself warns "no claim that LLM systems generically outperform markets."
- **Limitation**: short windows, small monthly selections (~10 names on S&P 100), one deployed system, pooled IC conflates fixed effects; authors stress significance is not reached on the longer cohort.

### 2411.04788v1 — Enhancing Investment Analysis: Optimizing AI-Agent Collaboration in Financial Research (2024)
- **Question**: how do agent group size and collaboration structure change financial-analysis quality?
- **Data/market**: 2023 10-K forms of 30 Dow Jones firms; three sub-tasks (fundamentals, sentiment, risk); GPT-4-1106.
- **Method**: AutoGen group chat with single/dual/triple groups and horizontal (peer), vertical (leader-subordinate), hybrid structures; 7 evaluation indicators (report quality + AIGC readability/coherence + one-week target price and buy/not-buy accuracy).
- **Headline**: for *simple* tasks (fundamental, sentiment) a **single agent beats multiple agents**; multi-agent helps on *complex* tasks (risk). For collaboration, all-agents-communicate wins on simple tasks; absolute leadership optimizes efficiency. The best overall configuration is an ensemble of agent groups: 2.35% average target-price error and 66.7% buy/not-buy accuracy, beating all other architectures.
- **Limitation**: LLM-as-judge scoring (1–5) for report quality; 30 firms, one report vintage; no costed backtest; multi-agent gains are architecture- and task-specific.

### 2602.07096v2 — REALFIN: How Well Do LLMs Reason About Finance When Users Leave Things Unsaid? (2026)
- **Question**: can models recognise when a financial question is under-specified and refuse to answer?
- **Data/market**: 2,020 bilingual (EN/CN) CFA/CPA-style questions, half full-condition and half with essential premises removed (macro assumptions, linking models, constraints, standards); 15 models (5 general, 5 finance-specific, 5 reasoning-enhanced).
- **Method**: three formulations — answer, recognise missing information, and reject unjustified options (none-of-the-above); zero-shot, temperature 0.
- **Headline**: consistent accuracy drops when conditions are missing; general-purpose models **over-commit and guess**, finance-specialised models fail to identify missing premises; reasoning-enhanced models sit in between. (The paper's own tables show the hardest category is complex calculation, and CN/EN gaps are large.) Reliable financial models must know when *not* to answer.
- **Limitation**: multiple-choice framing and a researcher-curated taxonomy; no live trading; prompts fixed zero-shot.

### 2511.08608v1 — When Reasoning Fails: Evaluating "Thinking" LLMs for Stock Prediction (2025)
- **Question**: do "thinking" LLMs (explicit/hidden reasoning traces) beat a direct LLM or classical learners on noisy, heavy-tailed, regime-switching returns?
- **Data/market**: NIFTY constituents; rolling 48-month train / 1-month test walk-forward, horizon k=1 day, universe U ∈ {5,11,21,36}; realistic IN costs (slippage, brokerage, STT, borrow).
- **Method**: gpt-4o-mini (direct) vs gpt-5 (TLLM, fixed 512-token budget) vs ridge/random forest, on ranking loss 1−IC, MSE, and costed long-short; DM/PT/SPA tests.
- **Headline**: as U grows under a fixed reasoning budget, the TLLM's ranking quality **deteriorates** while the direct LLM stays flat and classical learners are stable; TLLM variance is higher and needs ex-post winsorisation/blending; costed portfolios show **no net advantage** for the TLLM. H1 capacity-complexity mismatch, H2 reasoning variance, H3 domain misfit.
- **Limitation**: one market, one horizon, fixed B=512, no per-stock weight logs; conclusions explicitly conditional.

### 2304.05351v2 — The Wall Street Neophyte: A Zero-Shot Analysis of ChatGPT over Multimodal Stock Movement Prediction (2023)
- **Question**: can zero-shot ChatGPT predict stock movement from price features + tweets?
- **Data/market**: BIGDATA22 (50 stocks), ACL18 (87), CIKM18 (38), with historical price features and tweets.
- **Method**: binary up/down prediction, zero-shot and CoT prompts, with/without tweets; compared against LR/RF/LSTM/ALSTM/Adv-ALSTM/DTML and tweet methods (ALSTM-W/D, StockNet, SLOT).
- **Headline**: ChatGPT underperforms not only SOTA (DTML, SLOT) but also **logistic regression** on price features (e.g. BIGDATA22 ACC 53.13% vs SLOT 54.81%, MCC −0.025); CoT gives limited gains; tweets help in some datasets and hurt in others; explanations are superficial (price patterns + mis-read tweet sentiment). Explainability is the one advantage.
- **Limitation**: 2014–2020 datasets, 10-bar windows; the model is the 2023 GPT-3.5/4 API.

### 2603.19944v2 — Large Language Models and Stock Investing: Is the Human Factor Required? (2026)
- **Question**: are LLM stock recommendations reliable, and does prompting/oversight or regulatory-filing grounding help?
- **Data/market**: IBEX-35, 10 live monthly cycles April 2025–Jan 2026; ChatGPT, Gemini, DeepSeek, Perplexity; naïve, structured (multi-factor scoring), and human-supervised CoT prompts; CNMV filings uploaded monthly.
- **Method**: strict ex-ante information boundaries, fresh contexts each month, ex-ante long-short (top-5/bottom-5) portfolios; reasoning-quality taxonomy decoupled from realized returns.
- **Headline**: fluent narratives hide four recurring failure classes — stale/fabricated retrieved data, misinterpreted ratios (P/E, P/B, D/E read as "bad"), out-of-range aggregations and arithmetic errors, and opaque / non-self-correcting meta-reasoning. When guided and supervised, LLMs can outperform the market; grounding in official regulatory filings raises accuracy; CoT is an upper bound that requires iterative human correction.
- **Limitation**: 35-name index, 10 months, no quantitative error rates reported by design; small sample.

### 2603.20965v2 — Learning to Aggregate Zero-Shot LLM Agents for Corporate Disclosure Classification (2026)
- **Question**: does a trained aggregator beat single agents and voting over diverse zero-shot LLM judgments?
- **Data/market**: 18,420 US corporate disclosures (Nasdaq + S&P 500, 2018–2024), matched to next-day return direction; three ramped agents (Qwen2.5-3B/72B, Llama-3.2-3B) under performance/guidance/risk prompts.
- **Method**: each agent emits label+confidence+rationale; a logistic meta-classifier aggregates; chronological 60/20/20 split; compared to single agents, majority vote, confidence-weighted vote, FinBERT.
- **Headline**: balanced accuracy rises from 0.561 (best single agent = guidance) to 0.612 (aggregator), beating majority (0.573) and confidence voting (0.584). Gains are largest in **disagreement** regimes — 2–1 splits 0.558→0.603 and high-conflict 0.517→0.581 — while full-agreement cases gain only 0.642→0.651. Disagreement is structured information, not noise.
- **Limitation**: next-day return direction is a noisy target; the agent decomposition is researcher-designed; confidence is an imperfect proxy; small effect sizes.

### 2412.12148v1 — How to Choose a Threshold for an Evaluation Metric for Large Language Models (2024)
- **Question**: how should a deployment threshold on an LLM evaluation metric be chosen and justified?
- **Data/market**: HaluBench (~15k question/context/answer triplets with human hallucination labels); Faithfulness metric.
- **Method**: a model-risk-management recipe — identify application risks → stakeholder risk tolerance → translate to Type I/II error rates → derive the threshold by Z-score, KDE, empirical recall, ROC/AUC, or conformal prediction — with cross-validation; demonstrated on Faithfulness via several libraries.
- **Headline**: thresholds are a risk decision, not a metric-internal default; the paper gives statistically rigorous, reproducible recipes and shows the chosen method matters; the Z-score approach's normality assumption breaks for near-0/1 metrics like faithfulness.
- **Limitation**: threshold-selection methodology only; the "AI risk tolerance" elicitation has no settled method (acknowledged); one metric demonstrated.

### 2602.00082v1 — Design and Empirical Study of an LLM-Based Multi-Agent Investment System for Chinese Public REITs (2026)
- **Question**: can a multi-agent LLM closed loop (announcement/event/price-momentum/market → prediction → decision) improve risk-adjusted returns in low-volatility Chinese REITs?
- **Data/market**: 28 Chinese public REITs listed >1 year, backtest Oct 2024–Oct 2025, 0.03% per trade; DeepSeek-R1 vs fine-tuned Qwen3-8B (SFT + GSPO with a correctness+format reward).
- **Method**: four analyst agents feed a prediction agent (multi-horizon up/down/side probability) feeding a discrete-position decision agent; dynamic volatility threshold `θ_t` with square-root-of-time extension to T+5/T+20 defines "sideways"; teacher-model distillation builds SFT data.
- **Headline**: both agent paths beat buy-and-hold — CR 15.50%/13.75% vs 10.69%, Sharpe 1.71/1.77 vs 0.75, MDD ≈−4% vs −11%; the small fine-tuned model matches or beats the large general model on Sharpe; drawdowns smaller on ~100% of names.
- **Limitation**: 12 months, 28 funds, single market, no multiple-testing correction, only B&H as comparison; the strategy still cannot capture trend acceleration and draws down with the market in corrections.

### 2508.11152v1 — AlphaAgents: LLM-based Multi-Agents for Equity Portfolio Construction (2025)
- **Question**: can role-based multi-agent debate improve stock selection, and how does risk tolerance change behaviour?
- **Data/market**: 15 randomly chosen tech stocks, equal weights, initialized Feb 1 2024, 4-month monitored period; GPT-4o via AutoGen.
- **Method**: Valuation / Sentiment / Fundamental agents with role prompts and role-specific tools (vol/return calculator, summarization, 10-K RAG), a group-chat coordinator, and a round-robin debate to consensus; risk-averse vs risk-neutral vs risk-seeking agent prompts.
- **Headline**: the multi-agent portfolio outperforms single-agent (valuation, fundamental) portfolios on cumulative return and rolling Sharpe; the debate consolidates picks. Risk-profile prompting meaningfully separates risk-averse from risk-neutral, but the risk-seeking profile was **nearly indistinguishable** from risk-neutral and was dropped.
- **Limitation**: 15 stocks, 4 months, single sector; no statistical significance test; agent evaluation relies on human review of debate coherence plus RAG relevance metrics.

### 2605.05211v1 — A Review of LLMs for Stock Price Forecasting from a Hedge-Fund Perspective (2026)
- **Question**: what practical pitfalls does a hedge-fund lens expose in the LLM-forecasting literature?
- **Data/market**: survey of sentiment, report/transcript analysis, price tokenization, and multi-agent systems, cross-referenced against real deployment constraints.
- **Method**: critical review, with a worked illiquidity arithmetic and a τ of canonical leakage patterns.
- **Headline**: sentiment signals are regime- and source-dependent (the same macro print flips sign across regimes; a "Crystal Ball" study with next-day front-page knowledge yielded a 51.5% hit rate and 16% of participants going bust); datasets span too short a window (BigData22/CIKM18 ≈1 year, ACL18 ≈2); evaluation metrics (MSE/MAE/accuracy) are misaligned with P&L and reward pointwise price closeness; leakage arises from cross-day event drift, literal label statements ("TSLA tumbled…"), and peer/supply-chain spillover; a 10bp daily illiquidity premium cuts a 112.7% annual return to 65.5%, and a 0.2% daily cost can make a published strategy unprofitable; benchmark against transparent non-LLM (TA/ML) baselines over at least one full market cycle.
- **Limitation**: a review with illustration, not new empirics; some cited results are themselves underpowered.

## 3. Learnings applicable to this repo

### L1. Look-ahead must be structurally inexpressible, not merely discouraged in a prompt
- **Source**: `arXiv 2608.27734` (2026) — What survives honest evaluation?
- **Finding**: a planted look-ahead oracle (tomorrow's return) posts design SR 34.7 / eval SR 51.5 / DSR 1.00 and passes every statistical test; deflation corrects selection among *honestly computed* backtests but has no mechanism against a contaminated information set. Only a registry-validated action surface — where leaky features are excluded from the agent-selectable set — removes it. A text instruction "avoid look-ahead" fails because the execution environment still exposes the future.
- **Repo surface**: `tradingagents/strategies/alpha_zoo.py` (pure-expression evaluator + AST purity gate), `tradingagents/strategies/factor_expressions.py` (pure OHLCV factor engine), `tradingagents/strategies/backtest_engine.py`.
- **Status**: partial — the alpha-zoo AST purity gate exists, but it governs the alpha-zoo expression surface only; the analysts' free-text/tool path has no equivalent "look-ahead is inexpressible" boundary, and `data_quality.fundamentals_pit_ok` is per-read, not a construction-level gate.
- **Concrete step**: extend the alpha-zoo purity gate's registry flag into the tool catalog every analyst sees, so a leaky feature family is absent from the enumerations and server-side validation (not merely unwelcome in prose).

### L2. Deflated performance must be indexed to the search's own recorded trial count and Sharpe dispersion
- **Source**: `arXiv 2608.27734` (2026) — What survives honest evaluation?
- **Finding**: autonomy inflates the trial count — an agent that proposes/evaluates/refines performs dozens of implicit backtests before an operator sees a number; deflation must use recorded `N` and `V`, not an author estimate. The paper's "evaporation curve" shows the threshold overtaking the best in-sample Sharpe as trials accumulate; a pre-registered N=1 hypothesis faces almost no deflation.
- **Repo surface**: `tradingagents/strategies/trial_ledger.py::record` / `trial_stats`; `tradingagents/strategies/evaluate.py::deflated_sharpe` / `deflated_sharpe_report` (`sharpe_dispersion` path); `tradingagents/strategies/alpha_zoo.py`.
- **Status**: partial — the ledger and the closed-form deflation exist and `alpha_zoo` wires them, but `evaluate.deflated_sharpe` still takes `n_trials` from the caller and only reads ledger dispersion behind `enable_trial_ledger` (default off, `default_config.py:1166`), so a gate-off published number is the `sqrt(2 ln N)` independence approximation.
- **Concrete step**: make `deflated_sharpe_report` require an explicit provenance of its `N` (ledger or caller-asserted), and refuse to publish a deflated figure without it — the same honesty contract the ledger already applies to dispersion.

### L3. Any LLM evaluation over pre-knowledge-cutoff dates is non-identified and must be labelled or avoided
- **Source**: `arXiv 2504.14765` (2025) — The Memorization Problem
- **Finding**: GPT-4o recalls exact S&P 500 levels, unemployment to 0.1pp, and quarterly GDP before its cutoff; boundary instructions, masking, and fine-tuning-to-forget all fail; a post-cutoff backtest is the only clean test. Apparent accuracy on pre-cutoff data cannot distinguish skill from recall.
- **Repo surface**: `tradingagents/strategies/coverage_window.py` (window/survivor labelling), `tradingagents/strategies/data_quality.py::fundamentals_pit_ok`; (new logic in) the run manifest / `tradingagents/graph/trading_graph.py` provenance.
- **Status**: absent — `coverage_window` and `fundamentals_pit_ok` guard *data* point-in-time, but nothing in the repo knows an LLM's knowledge cutoff, so a historical LLM backtest can silently be a memorization test.
- **Concrete step**: add a per-run `llm_knowledge_cutoff` field and have the honest-evaluation gates mark any evaluation window entirely before it as `contaminated_pre_cutoff` (a third label beside `SURVIVOR_ONLY`), never publishing a pre-cutoff "alpha".

### L4. Ground numeric claims in a computed read; RAG and tool-calling work where few-shot and decoding tricks do not
- **Source**: `arXiv 2311.15548` (2023) — Deficiency of LLMs in Finance
- **Finding**: GPT-4 returns *stale* facts (a delisted symbol quoted as live) and confidently wrong expansions; few-shot and DoLa give limited relief, while retrieval augmentation and prompt-based tool learning produce the correct query/value. Domain fine-tuning even degrades instruction-following.
- **Repo surface**: `tradingagents/strategies/debate_claim.py::verify_claim` (L1 hard verifier against ground-truth keys), `tradingagents/agents/utils/report_verifier.py` (GROUNDED/UNSUPPORTED/CONTRADICTED per claim), `tradingagents/agents/utils/analysis_tools.py` (the computed `@tool` surface).
- **Status**: shipped — the L1 claim verifier resolves debater labels to canonical computed keys with an alias/fuzzy fallback and marks unresolvable claims `unverified`; the report verifier adds a per-claim pass over the same evidence leaves with deterministic numeric anchoring after the LLM.
- **Concrete step**: none needed for the mechanism; the exposure is calibration — feed `verify_claim`'s `unverified`/`abstain` counts into `calibration.scorecard` so unresolved claims visibly lower the agent's score instead of being dropped.

### L5. Hallucination in this domain is stale entities and misread ratios, not fabrications alone
- **Source**: `arXiv 2603.19944` (2026) — Is the Human Factor Required?; `arXiv 2311.15548` (2023)
- **Finding**: the recurring failure taxonomy is (A) stale/fabricated retrieved data, (B) misinterpreted fundamentals (lower P/E, P/B, D/E read as "bad"), (C) out-of-range aggregations and arithmetic errors, (D) opaque, non-self-correcting meta-reasoning. Entity mismatch (wrong company's statements) is a documented observed error.
- **Repo surface**: `tradingagents/strategies/ratios.py`, `tradingagents/strategies/dupont.py`, `tradingagents/strategies/integrity_tools.py::thesis_evidence_matrix`, `tradingagents/agents/utils/price_consistency.py`.
- **Status**: partial — ratio computation is deterministic and the thesis-vs-evidence matrix exists, but there is no check that a *lower* P/E is not being narrated as bearish, and no entity-identity binding across a report's figures.
- **Concrete step**: add a direction-sanity pass in the claim verifier that flags any claim whose qualitative sign contradicts the computed metric's known orientation (cheapness vs risk) for ratios on a declared direction table.

### L6. Multi-agent aggregation should weight agents by measured reliability and treat disagreement as signal, not noise
- **Source**: `arXiv 2603.20965` (2026) — Learning to Aggregate Zero-Shot LLM Agents
- **Finding**: a trained logistic aggregator over label+confidence+rationale beats every single agent, majority vote, confidence-weighted vote and FinBERT (balanced accuracy 0.612 vs 0.561 best single, 0.573 majority, 0.584 confidence); the gains concentrate in 2–1 splits (0.558→0.603) and high-conflict cases (0.517→0.581) and nearly vanish under full agreement.
- **Repo surface**: `tradingagents/strategies/consensus.py::weighted_consensus` / `should_hold`, `tradingagents/strategies/calibration.py::scorecard`, `tradingagents/strategies/debate_score.py`, `tradingagents/strategies/score_disagreement.py::risk_disagreement`.
- **Status**: partial — `weighted_consensus` accepts calibration-derived weights and `consensus.should_hold` thresholds a weak consensus to HOLD; but the aggregator is a fixed weighting rule, not a learned function of disagreement *structure*, and confidence is used as supplied rather than measured.
- **Concrete step**: make the arbitration weight a function of the agent's measured `calibration.scorecard` hit rate per horizon (already computed) rather than 1.0, and record the agreement regime (unanimous / 2–1 / conflict) on every emitted decision so the conflict cases — where the literature says the edge is — stay identifiable.

### L7. Sample independent opinions before cross-talk; consensus pressure degrades accuracy
- **Source**: `arXiv 2411.04788` (2024) — Optimizing AI-Agent Collaboration; `arXiv 2603.20965` (2026)
- **Finding**: for simple tasks a single agent beats a group; multi-agent helps only for complex tasks, and an all-communicate structure is best for simple tasks while a leader structure is merely efficient. Aggregation over independent views is what carries the signal; debate should stress-test, not manufacture consensus.
- **Repo surface**: `tradingagents/agents/utils/independent_vote.py` (pre-debate stances, `RISK_ROLES`/`RESEARCHER_ROLES`, `computed_independent_vote`), `tradingagents/strategies/consensus.py::agreement_score`, `tradingagents/strategies/debate_score.py::entrenchment_index` / `reweight_to_baseline`.
- **Status**: shipped — `independent_vote` samples three risk debators + two researchers *before* any transcript, and `debate_score` has explicit entrenchment/artificial-consensus machinery. Gate `enable_independent_vote` is default False (`default_config.py:937`).
- **Concrete step**: record `agreement_score` on *both* the pre-debate independent distribution and the post-debate verdict, and surface the gap as a computed entrenchment read on the decision card.

### L8. A quant-only baseline is the control that decides whether the LLM adds value
- **Source**: `arXiv 2304.05351` (2023) — Wall Street Neophyte; `arXiv 2511.08608` (2025) — When Reasoning Fails
- **Finding**: zero-shot ChatGPT underperforms classical learners including plain logistic regression on price features, and CoT gives limited gains; a fixed-budget "thinking" LLM degrades as cross-sectional complexity grows while a direct LLM and ridge/random forest stay stable, with no costed net advantage. Without a quant-only control, "the LLM beat buy-and-hold" is uninformative.
- **Repo surface**: `tradingagents/strategies/quant_baseline.py::quant_signal` / `baseline_rating` (W1-5 deterministic LLM-free stack), `tradingagents/strategies/prediction_ledger.py`, `tradingagents/strategies/evaluate.py`.
- **Status**: absent — `quant_signal`/`baseline_rating` exist but grep across `tradingagents/` and `scripts/` finds **no non-test consumer**; the W1-5 baseline is built and never run beside the LLM ratings.
- **Concrete step**: wire `baseline_rating` into the same scored ledger path as the PM rating (quant-only vs quant+LLM vs LLM-only), and publish the three side by side in the run card.

### L9. Models systematically over-commit on under-specified financial questions; abstention must be a first-class outcome
- **Source**: `arXiv 2602.07096` (2026) — REALFIN
- **Finding**: with essential premises removed, accuracy drops and general models guess while finance-specialised models fail to flag the missing information; a reliable model must know when a question should not be answered, and none-of-the-above exposes pattern-matching.
- **Repo surface**: `tradingagents/strategies/refusal_ledger.py` (TIERS, `log_refusal`, forward sampler), `tradingagents/strategies/debate_claim.py` (`ABSTAIN` status), `tradingagents/strategies/decision_guardrail.py::score_band_for`.
- **Status**: partial — `refusal_ledger` records gate refusals and scores them forward, and `claim` has an `ABSTAIN` verdict, but there is no path that *abstains a decision* for missing premises (missing metric, stale vendor, no news) the way REALFIN demands. `degrade_triple` in `news_relevance` treats "no news" as distinct from "search failed", which is the right primitive.
- **Concrete step**: when `data_quality.aggregate_quality` drops to the `reduced`/`none` tier or a required premise (options data, fundamentals period) is `unavailable`, emit an explicit abstain/hold decision through the refusal ledger rather than letting the debate proceed on defaults.

### L10. A metric threshold is a risk decision, and its calibration method matters
- **Source**: `arXiv 2412.12148` (2024) — How to Choose a Threshold for an Evaluation Metric
- **Finding**: thresholds should flow from stated application risks → stakeholder risk tolerance → Type I/II error rates → a statistically rigorous cut (ROC/conformal/empirical-recall), cross-validated; the naive Z-score assumes normality that near-bimodal metrics like faithfulness violate.
- **Repo surface**: `tradingagents/strategies/calibration.py::calibration_table` / `scorecard`, `tradingagents/strategies/alpha_eval.py::ceiling_ratio` (falsifier gate), `tradingagents/strategies/evaluate.py`.
- **Status**: partial — the repo calibrates confidence bins and has an R²_OOS ceiling falsifier, but the pass/fail thresholds on LLM-output metrics (claim-validity share, evidence quality) are fixed constants rather than risk-derived and cross-validated cuts.
- **Concrete step**: make the debate/verifier thresholds explicit risk parameters (per-metric, cross-validated) and record the chosen Type I/II trade-off beside every published gate statistic, as the ledger modules already do for counts.

### L11. Grounding in official regulatory filings raises accuracy; prompt strategy and oversight dominate outcomes
- **Source**: `arXiv 2603.19944` (2026); `arXiv 2603.20965` (2026)
- **Finding**: uploading official (CNMV) filings improved recommendation accuracy; a structured prompt with two metrics per driver and human-supervised CoT outperformed naive prompting; the same held for disclosure classification, where the guidance-focused prompt was the strongest single agent.
- **Repo surface**: `tradingagents/strategies/news_relevance.py::score_news_article` / `admit_article` (OFFICIAL_HOSTS boost, `degrade_triple`), `tradingagents/strategies/evidence_gather.py`, `tradingagents/agents/utils/analysis_tools.py`.
- **Status**: shipped — `news_relevance` deterministically boosts official sources (sec.gov, nasdaq.com, nyse.com, …) and admits them outright, and the news admission is gated by content rather than a domain blacklist.
- **Concrete step**: none needed; the gap is measurement — log per-report which evidence leaves came from official sources so the run card can condition accuracy on filing-grounded vs news-only claims.

### L12. Multi-agent equity alpha must be validated against a matched random-selection null, and attribution needs a collinearity-aware decomposition
- **Source**: `arXiv 2604.17327` (2026) — Signal or Noise
- **Finding**: only the Monte Carlo null (same universe/date/count/weighting, 10,000 draws) separates selection skill from universe/timing effects; the S&P 100 cohort's excess is *not* significant (p=0.17); and cosine attribution is misleading because agent embeddings are collinear (0.46–0.79) — joint NNLS reallocates weight away from the high-cosine but zero-IC News agent. The single most-cosine agent can carry no predictive content.
- **Repo surface**: `tradingagents/strategies/report_attribution.py::attribution` (NNLS projection, this paper's construction), `alpha_eval.py`, `alpha_health.py`, `evaluate.py`.
- **Status**: shipped/partial — `report_attribution.attribution` already implements the NNLS projection and explicitly refuses a pseudo-embedding when no embedder is present; the Monte-Carlo matched-null portfolio test is not implemented.
- **Concrete step**: add a matched-random-selection null to `evaluate.py` (draw the engine's monthly holdings count from the same PIT universe and compare compound return), so a "strong-buy" cohort is judged against selection luck rather than only against buy-and-hold.

## 4. Where this repo is already ahead of the literature

- **Pre-debate independent sampling** (`tradingagents/agents/utils/independent_vote.py`): the corpus only aggregates post-hoc (2603.20965) or shows that naive debate hurts (2411.04788); this repo samples each debator's stance *before* any transcript to avoid consensus pressure, then runs the debate as a stress-test layer — a stronger design than anything read here.
- **A deterministic L1 claim verifier** (`debate_claim.py::verify_claim` with canonical-key resolution, alias map, and a threshold-gated fuzzy fallback): the corpus's grounding claims are "RAG reduces hallucination"; this is a per-claim, key-resolved, tolerance-based hard verifier that never lets an unresolvable claim become valid.
- **Search-integrity ledgers** (`trial_ledger.py`, `refusal_ledger.py`, `prediction_ledger.py`): immutable append-only rows with `returns_sha` identity, missing-data-as-`unavailable` (never 0), and the refusal forward-sampler with the "*missed beats saved*" conservative tie-break. 2608.27734 asks for exactly this and 2607.02830 supplies only the taxonomy; the repo has both plus the null-safe read.
- **Coverage-window refusal** (`coverage_window.py` + `data_quality.panel_statistic`): refuses a panel statistic padded by pre-listing positions, naming the alignment rather than assuming it — the exact bias 2603.20237 formalizes.
- **A falsifier-only accuracy ceiling** (`alpha_eval.py::ceiling_ratio`, explicitly "never a validator", with an out-of-sample GARCH σ̂): the corpus's honest-evaluation papers mostly *warn*; this is a computed inequality that can flag an impossible point.
- **Non-negative attribution with an explicit no-embedder refusal** (`report_attribution.py`): refuses to substitute a bag-of-words pseudo-embedding where 2604.17327 would embed text — a stronger honesty contract than the source paper.
- **Numeric anchoring after the LLM** (`agents/utils/report_verifier.py`): deterministic figure matching downgrades UNSUPPORTED→GROUNDED and CONTRADICTED→UNSUPPORTED so verdicts never depend on the model's arithmetic.

## 5. Defects or risks the literature exposes

1. **The quant-only baseline is dead code.** `tradingagents/strategies/quant_baseline.py::quant_signal`/`baseline_rating` (W1-5) has no non-test caller (verified by grep across `tradingagents/` and `scripts/`). 2304.05351 and 2511.08608 both show LLMs failing to beat classical learners, so the repo currently cannot answer "does the LLM add value?" with its own computed control.
2. **Deflation is caller-asserted by default.** `tradingagents/strategies/evaluate.py:161-186` accepts `n_trials` from the caller and only uses the trial ledger's measured dispersion behind `enable_trial_ledger` (`evaluate.py:153`, default off at `tradingagents/default_config.py:1166`). 2608.27734's central claim is that autonomy inflates the trial count and deflation must be indexed to the *recorded* search; online, a published deflated Sharpe is still the independence approximation.
3. **No LLM knowledge-cutoff guard.** Nothing in `tradingagents/` records a model cutoff date. 2504.14765 proves that on pre-cutoff dates forecasting ability is non-identified; any historical LLM backtest in this repo can therefore be a memorization test wearing an alpha label. `coverage_window.py` guards panel padding, not model memory.
4. **News pipelines have no event-level fold or literal-label filter.** `news_relevance.py::admit_article` admits by host/content but there is no per-event timestamp fold and no filter for text that states a realized move ("TSLA tumbled…"), the two leakage patterns 2605.05211 names. Random train/test splits over multi-day news events will leak the label.
5. **Report thresholds are fixed constants, not risk-derived.** The claim-validity/evidence gates compare against hard-coded tolerances (e.g. `debate_claim.py::_DEFAULT_TOLERANCE_PCT = 5.0`, `_FUZZY_THRESHOLD = 0.72`) with no recorded Type I/II trade-off, against 2412.12148's prescription. `calibration.py` calibrates confidence but not the gate thresholds.
6. **No prompt-sensitivity harness.** 2603.19944 and 2304.05351 show results swing with prompting strategy and 2605.05211 notes finance-embedding prompt sensitivity; the repo has persona/role prompts (`debate_roles.py`, `analyst` prompts) but no repeated-run measurement of decision stability across prompt variants.
7. **Underpowered multi-agent claims are easy to reproduce internally.** 2411.04788 shows more agents can hurt simple tasks and 2604.17327's longer cohort is insignificant (p=0.17); `enable_debate` defaults off and `max_debate_rounds`/`max_risk_discuss_rounds` default to 1 (`default_config.py:651-662`), so the repo is not currently at risk of round inflation — but any future raising of agent counts should be justified against this evidence, not intuition.
8. **"Thinking" models are adopted without a measured edge.** 2511.08608 finds no costed net advantage for a reasoning-budgeted LLM over a direct LLM or ridge/RF on short-horizon ranking. The repo's per-role model mapping (`agents/utils/debate_roles.py`, `resolve_role_llm`) can route to reasoning models; without `quant_baseline` wired and `llm_cost` surfaced in the run card, that choice is untested and unmeasured.

## 6. Limits of this review

- I read 17 papers in full text (abstract through results/limitations): 2608.27734, 2504.14765, 2601.06088, 2606.22719, 2311.15548, 2304.07619, 2604.17327, 2411.04788, 2602.07096, 2511.08608, 2304.05351, 2603.19944, 2603.20965, 2412.12148, 2602.00082, 2508.11152, 2605.05211.
- The category's 134 rows were sampled via the sweep's annotation and the top-60 booklist, both relevance-ranked; the medium/low tiers (74/40 rows) were not read beyond the evidence-pack takeaway. Several high-relevance sentiment-extraction papers (`2507.18417`, `2508.07408`) were skipped once the deep-read set already covered the sentiment theme through the reviews.
- `2407.17866v3` (Financial Statement Analysis with LLMs, Kim/Muhn/Nikolaev) is listed in the booklist but its PDF is **not present** in `E:/fin paper/`; it could not be read. It is also the one listed paper whose own comment records a temporary withdrawal over replication inconsistencies — itself a reproducibility data point I could not verify in full text.
- Repo status claims were verified by reading the named module and, where wiring mattered, by grep for non-test callers. I did not run any tests, linters, or the engine; "shipped" means the symbol and a plausible call path exist and were read, not that a live run was observed.
- The corpus is a snapshot ending early 2026; 2026's count (33) will understate the year. Several 2026 venue/preprint ids cite models (GPT-5.x, Claude-Sonnet-4.5) whose behaviour is not reproducible from the PDFs, and I take their reported numbers at face value.
