# News, Sentiment & Textual Signals

`book 04/19` · slug `sentiment-text` · 341 papers in the corpus · 46 rated high-relevance by the sweep

## 0. Scope

This category covers the extraction of directional, attentional and event signals from financial text — news wires, social media, earnings calls, SEC filings — and the empirical question of whether those signals predict returns and volatility, and for how long. It is the single most directly wired category in this repo: `news_relevance`, `news_score`, `sentiment`, `sentiment_score`, `sentiment_research`, `text_factors`, `events` and `catalyst` are all text-facing calculators, and four agents (news, social, market, fundamentals) consume them. The category matters both for what it validates (the repo's declared-tone/attention/event decomposition is close to the literature's consensus) and for what it warns against (LM dictionary sign, un-deflated text-factor backtests, and reading a same-day sentiment/return correlation as predictability).

## 1. Corpus composition

The evidence pack records **341** swept rows for this category: **46 high**, **206 medium**, **89 low**. The top-60 booklist (used for selection below) is a near-contemporary sample: only 6 of 60 predate 2020, and none predates 2011.

| decade | booklist papers |
| --- | --- |
| 2010–2019 | 6 |
| 2020–2026 | 54 |

By arXiv primary category the booklist is dominated by empirical statistical finance, with an NLP-second literature grafted on:

| primary category | count |
| --- | --- |
| q-fin.ST (statistical finance) | 38 |
| cs.CL (computation & language) | 11 |
| cs.LG | 2 |
| econ.GN | 2 |
| q-fin.MF / q-fin.PM / q-fin.RM / cs.AI / cs.CE / cs.SI / physics.soc-ph | 1 each (7 total) |

The category is dominated, first, by the "does text predict returns?" question posed on a new data source or a new language model (the cs.CL half), and second, by the application of transformer sentiment to an index or a small basket. Genuine measurement papers — event-time returns, multiple-testing correction, aggregation-level ablation — are the minority but carry the highest reuse value. Crypto and non-US markets (China, India, Nigeria, Iran, Russia) are heavily represented; only the equity/US-feed papers are directly reusable here.

## 2. Deep reads

### arXiv 2608.14014v1 — Buy the Rumor, Sell the News: When Is News Priced In? (2026)
- **Question**: do "news is already priced in" and "buy the rumor, sell the news" hold, for which event types, and by how much?
- **Data/market**: 4.57M US financial news articles, ~3,000 stocks, 2023–2026; 1.68M (stock, day, tag) events; 364,405 neutral-sentiment events as a placebo; daily beta-adjusted abnormal returns.
- **Method**: GPT teacher distilled into a compact classifier (95% agreement), 17 event tags + 5 attributes, story clustering to separate first reports from follow-up, bootstrap significance resampling trading dates; a background-drift adjustment net of the neutral placebo.
- **Finding**: the news-aligned move concentrates before/at publication — pooled, the move by the close of publication day is **2.8×** its value 20 days later, and for rumor-flagged events the rumor day captures the entire move. Net of the placebo drift, markets **underreact to quantified fundamental news** (earnings +0.22%, guidance +0.13%, analyst +0.10% over days +6..+20) and **overreact to soft stories** (product launch −0.18%, leadership −0.18%, macro-through-stock −0.34%).
- **Limitation**: tags are retrospective descriptive labels; the background-drift correction is a benchmark residual, not an identified factor; results are for large/mid US coverage, not the long tail.

### arXiv 2506.06329v1 — The Hype Index: an NLP-driven Measure of Market News Attention (2025)
- **Question**: can media *attention* be separated from tone and turned into a signal?
- **Data/market**: S&P 100 constituents, LSEG/Refinitiv headlines, Dec 2023–Apr 2025 (326 trading days), GICS sectors.
- **Method**: a News Count-Based Hype Index (share of articles mentioning a name) and a Capitalization Adjusted Hype Index (media weight ÷ market-cap weight), at stock and sector level; classification into hype clusters; lagged association with returns, volatility and VIX.
- **Finding**: Financials and IT are consistently over-covered (3–4× average); the cap-adjusted version **re-ranks sectors materially** — IT moves from "over-hyped" to "less prominent" once its economic size is accounted for, while Real Estate and Utilities become relatively hyped. The index is non-normal (all normality tests reject), and is pitched as a volatility/short-term signalling input.
- **Limitation**: entity mapping is the vendor's proprietary NER and is not corrected; only 326 days; the raw and cap-adjusted indices are 0.82–0.98 correlated, so the "adjustment" is largely a level shift.

### arXiv 2607.14174v1 — How Much of a 10-K Matters? Aggregation-Dependent Value of Full-Text versus Risk-Factor Sentiment (2026)
- **Question**: for 10-K text, and for return vs volatility targets, does the full filing or the Item 1A risk-factor section carry more sentiment signal, and at what aggregation level?
- **Data/market**: 1,383 10-K filings, 94 Nasdaq-100 technology firms, 2006–2023; twelve sentiment metrics (2 document variants × 2 targets × 3 levels).
- **Method**: supervised lexicon-learning (Ke et al.) trained against return and volatility labels; sector/portfolio series Kalman-smoothed; Pearson correlation against a Loughran–McDonald dictionary baseline and price.
- **Finding**: full-filing text wins at sector and portfolio level by 2–5 pp; the reversal at firm level favours Item 1A (+1 pp return, +6 pp volatility). **The LM dictionary baseline is strongly, consistently negatively correlated with price at every level tested** (sector r = −0.910; portfolio r = −0.841 to −0.937). Risk-factor text surfaces themes (supply-chain risk, covid, biotech) the full text dilutes.
- **Limitation**: bag-of-words (no n-grams); equally-weighted aggregates ignoring index weights; human-authored theme interpretation; a single technology universe.

### arXiv 2607.06220v1 — Stable Sentiment and Persistent Dynamics in U.S. Economic News over 45 Years (2026)
- **Question**: has the *response time* of news sentiment changed, independent of its average level?
- **Data/market**: 24 US newspapers, daily Shapiro et al. economic-news sentiment index, 1980–2025 (16,737 days).
- **Method**: detrended fluctuation analysis (Hurst exponents) with seasonality removal and a Hampel filter, rolling-window exponents regressed on calendar time across pre-web/web/social-media eras; a minimal endogenous-memory model (fractional-Gaussian slow component + AR(1) shocks).
- **Finding**: average tone is stable but **persistence rose**: short-scale H ≈ 0.67, long-scale H ≈ 0.95; daily shocks are mildly anti-persistent (H ≈ 0.43 at 2–8 days) but mean-revert more slowly over time; negative sentiment bursts last longer. Sentiment is a persistent **episode**, not a daily reaction that resets.
- **Limitation**: one lexicon-based index; cannot fully control for article volume, topic mix, semantic drift or editorial routines; changes in the index's temporal organisation are not claims about public emotion.

### arXiv 2503.03612v4 — Large language models in finance: what is financial sentiment? (2025)
- **Question**: what is "financial sentiment", and how do LLM families estimate it?
- **Data/market**: survey/review — no new dataset.
- **Method**: traces market-based → survey → lexicon (LM) → ML → transformer methods; contrasts BERT-type (bidirectional classification) with GPT-type (autoregressive generation).
- **Finding**: BERT-type (RoBERTa/FinBERT) model outputs are a probability over three classes, not an intensity; GPT-type models generate explanations and adapt to regimes but produce systematically different scores for the same text. The field has **no unified sentiment definition**, so different indices conflict; multi-source/hybrid integration is the current best practice.
- **Limitation**: a survey, not evidence; its central claim (definitional non-reproducibility) is a warning, not a method.

### arXiv 2306.12659v1 — Instruct-FinGPT: Financial Sentiment Analysis by Instruction Tuning of General-Purpose LLMs (2023)
- **Question**: can instruction tuning a small general LLM beat SFT finance models at sentiment, particularly on numbers and context?
- **Data/market**: public financial sentiment datasets; LLaMA base.
- **Method**: convert classification data into instruction/generation data; fine-tune; map generations back to labels.
- **Finding**: instruction tuning **outperforms both general LLMs (ChatGPT/LLaMA) and SOTA supervised sentiment models**, notably where numerical understanding and context matter, at <$300 of training vs BloombergGPT's ~1.3M GPU-hours/$5M.
- **Limitation**: evaluated on sentiment classification only; no portfolio/return evaluation; small fine-tuning corpus; the "numerical sensitivity" fix is asserted, not separately ablated.

### arXiv 2507.18417v1 — FinDPO: Financial Sentiment Analysis for Algorithmic Trading through Preference Optimization of LLMs (2025)
- **Question**: does human-preference alignment (DPO) beat supervised fine-tuning for financial sentiment, and can a causal LLM feed a portfolio?
- **Data/market**: 32,970 labeled samples (FPB, TFNS, NWGI); 204,017 news articles, 417 S&P 500 names, Feb 2015–Jun 2021.
- **Method**: DPO + LoRA (rank 16) on Llama-3-8B-Instruct, single A100, 4.5 h; a **logit-to-score converter** (softmax over the sentiment classes at the first generated token, temperature-scaled) to make a discrete classifier rankable; 35% long / 35% short equal-weight portfolio.
- **Finding**: FinDPO weighted F1 **0.846**, +11% over FinGPT v3.3; 67% annual return, Sharpe 2.0 **after 5 bps costs**; all lexicon baselines look strong only before costs — frictionless evaluation is the literature's key over-optimism.
- **Limitation**: overconfidence in raw logits required temperature calibration; one base model; NER filtering drops 24% of scraped articles; results are a simulation, not live.

### arXiv 2606.03457v1 — Hybrid News Sentiment Engine: Real-Time Market Analysis via Adaptive Ensemble Learning on News–Price Pairs (2026)
- **Question**: can sentiment be calibrated to *realized* price reactions cheaply, on CPU, without retraining?
- **Data/market**: Tradeflags NewsFeed, 22 price-snapshot fields per item (ES/NQ/SPY/CL/BTC/ETH), 3-hour cron cycle.
- **Method**: three-way ensemble — FinBERT-style lexicon, adaptive TF-IDF headline clustering whose centroids track average realized price reaction, and auto-calibrating weights re-fit every 6 h against the realized move; compared against FinBERT, GPT, VADER, commercial APIs on cost/latency/accuracy/adaptability.
- **Finding**: a CPU-only, sub-second pipeline with no GPU is feasible; the **realized-price-reaction supervisory signal for ensemble weights** is presented as novel, and the staleness critique (a "rate hike" is bearish in 2022, benign in 2026 at the same text) is the strongest argument against frozen classifiers.
- **Limitation**: a deployed-systems paper, not a controlled study; no held-out accuracy table; single vendor feed; cluster pruning and weight rules are heuristics.

### arXiv 2203.12460v1 — An Exploratory Study of Stock Price Movements from Earnings Calls (2022)
- **Question**: do earnings-call semantics predict post-call price moves better than hard data or analyst ratings?
- **Data/market**: ~100,000 transcripts, 6,300 public companies, Jan 2010–Dec 2019; daily/weekly/sector-index-relative labels.
- **Method**: descriptive sentiment analysis; a graph neural network over transcript semantic features; comparison against sales/EPS surprises and pre-earnings analyst recommendations.
- **Finding**: pre-call analyst buy/sell/hold ratings correlate **weakly** with post-call moves; transcript semantics predict direction reliably across five sectors, and **beat actual/estimated sales and EPS** in most cases (≥10% higher recall, 33% higher precision in Technology and Services).
- **Limitation**: exploratory; sector-specific models; labels are directional (binary) not magnitude; no transaction-cost or tradability analysis.

### arXiv 1112.1051v1 — Predicting Financial Markets: Comparing Survey, News, Twitter and Search Engine Data (2011)
- **Question**: across data sources and sentiment instruments, which has genuine predictive value, once all are controlled for each other?
- **Data/market**: DJIA, trading volume, VIX, gold; Twitter feeds, news headlines (LM negative lexicon), Google Insights searches, traditional surveys (Investor Intelligence, DSI).
- **Method**: construct five sentiment indicators; regress market values on them jointly, controlling for VIX.
- **Finding**: traditional survey sentiment is a **lagging** indicator and becomes statistically insignificant once other mood indicators and VIX are controlled; weekly Google search volumes and 1–2-day-old Twitter sentiment/term frequencies remain significant predictors of daily log return.
- **Limitation**: short sample (2010–2011); weekly vs daily scale clashing; single-index; the "significance" is not out-of-sample tradability.

### arXiv 2012.05906v1 — A Sentiment Analysis Approach to the Prediction of Market Volatility (2020)
- **Question**: does news/tweet sentiment correlate with next-day FTSE100 return and volatility?
- **Data/market**: 969,753 RavenPack headlines, ~12,000 Eikon news stories, 545,979 cashtagged tweets, Jan–Aug 2019; FTSE100.
- **Method**: VADER sentiment scoring; correlation and Granger causality; LDA topic features added to a directional-volatility classifier.
- **Finding**: headline sentiment is significant for **returns** (negative news vs closing return), but headline/full-story sentiment has **no or weak correlation with volatility**; tweet positive sentiment and next-day volatility correlate at **−0.7** (p<0.05); sentiment + LDA topic features reach **63%** directional volatility accuracy.
- **Limitation**: only ~8 months and one index; weekend/holiday aggregation by carry-forward; per-source results are unstable and the authors themselves invoke "buy on rumor, sell on news".

### arXiv 2304.07619v6 — Can ChatGPT Forecast Stock Price Movements? Return Predictability and Large Language Models (2025 version)
- **Question**: can an off-the-shelf LLM read headline economic content, and what does its accuracy reveal about market underreaction?
- **Data/market**: news headlines for 4,123 US stocks, Oct 2021–May 2024 (post-GPT-4 knowledge cutoff), daily rebalanced.
- **Method**: zero-shot GPT-4 headline classification; overnight/intraday split; long-short drift strategy; topic-model interpretability; comparison across 12 LLMs and against embedding-based supervised models; a theoretical underreaction/limits-to-arbitrage model.
- **Finding**: GPT-4 hit rates ~90% for the non-tradable initial reaction; its scores predict subsequent drift, strongest for **small stocks and negative news**; strategy returns 34 bps/day pre-cost; annualized Sharpe **2.97** overall, but **declining from 6.54 (2021Q4) to 1.22 (Jan–May 2024)** as LLM adoption rose; embedding models collapse with small training samples while GPT-4 does not.
- **Limitation**: the initial reaction itself is not tradable; exploitation needs market-maker-level costs; topic interpretability is suggestive; adoption-decay evidence is indirect.

### arXiv 2608.23808v2 — Equity Strategy Backtesting: Luck or Edge? The MinervaScore as a Statistical Robustness Grade (2026)
- **Question**: how should a selected strategy be graded for search luck rather than raw Sharpe?
- **Data/market**: 359,062 production backtest records; synthetic markets with known ground truth; a pre-registered real-market hold-out.
- **Method**: combine Deflated Sharpe Ratio, Probability of Backtest Overfitting, Superior Predictive Ability and Minimum Track Record Length with a regime-stability diagnostic; logit-transform bounded quantities; 0–100 display gated by all five passing.
- **Finding**: separates genuine edge from lucky backtests at **AUROC 0.989**; the corrected DSR alone is the strongest single signal (most of the composite's discrimination), and the composite's value is battery coverage and verdict consistency. In the **pre-registered real-market test the score had no significant forward relationship** (Spearman ρ = 0.013, p = 0.40) — it is a reporting/audit layer, not evidence of predictability.
- **Limitation**: the developers themselves report the null real-market result; results depend on a synthetic ground-truth generator; the GT-Score comparison is a proxy.

### arXiv 1507.06477v1 — Novel and topical business news and their impact on stock market activities (2015)
- **Question**: do markets respond to *novel* news, and separately to *topical* (widely republished) news?
- **Data/market**: >90M English business-news articles (Reuters, DJ, wires), minute-by-minute NYSE/NASDAQ prices, 2003–2014.
- **Method**: novelty = no linguistically similar earlier article; topicality = number of similar articles carried by *other* agencies; correlate with intraday transaction count and volatility.
- **Finding**: stock prices and transaction volumes respond significantly **only when an article is both novel and topical**; breaking-news alerts move prices far more than ordinary headlines, with an exponential response decay (~exp(−0.073·Δt)).
- **Limitation**: pre-LLM string-similarity novelty; headline-level only; no cross-sectional neutralisation or cost analysis.

### arXiv 2603.11408v2 — Beyond Polarity: Multi-Dimensional LLM Sentiment Signals for WTI Crude Oil Futures Return Prediction (2026)
- **Question**: does multi-dimensional sentiment (relevance, polarity, intensity, uncertainty, forwardness) beat polarity-only for weekly oil returns?
- **Data/market**: AlphaVantage energy news, 29,153 articles 2020–2025 (20% stratified sample = 8,639); weekly WTI log returns; 314 weeks, 166 up / 147 down.
- **Method**: extract five dimensions with GPT-4o, Llama 3.2-3b, FinBERT, AlphaVantage; weekly aggregation; LightGBM classifier; SHAP interpretability.
- **Finding**: best result from **combining GPT-4o and FinBERT** — LLM and conventional models are complementary; SHAP shows **intensity and uncertainty** are among the most important predictors, so predictive content extends beyond polarity.
- **Limitation**: small stratified sample for cost; weekly horizon only; a single commodity; no economic (cost-adjusted) evaluation.

## 3. Learnings applicable to this repo

### L1. Sentiment half-life is event-class-specific, not one global constant
- **Source**: `arXiv 2608.14014v1` (2026) — Buy the Rumor, Sell the News; `arXiv 2607.06220v1` (2026) — Persistent Dynamics.
- **Finding**: by event tag the post-publication trajectory diverges — quantified fundamental news still drifts at days +6..+20 (earnings +0.22%, guidance +0.13%, analyst +0.10%) while soft news reverses by the same window (launches −0.18%, macro −0.34%); pooled, the move by publication close is 2.8× its 20-day value. Sentiment is a persistent episode whose memory is long-scale (H ≈ 0.95).
- **Repo surface**: `tradingagents/strategies/sentiment.py::decayed_weight` (default `half_life=7.0`) and `tradingagents/strategies/news_score.py::news_persistence` (`PERSISTENCE_HALF_LIVES = (7.0, 14.0, 30.0)`).
- **Status**: `partial` — a single default half-life plus a fixed multi-lambda set exist, but nothing varies them by event class.
- **Concrete step**: add a DECLARED `EVENT_HALF_LIFE_DAYS` mapping keyed on `FORM_EVENT_SCORES`/tag vocabulary (long for earnings/guidance/analyst, short for launch/macro/promotional) and have the news path pass the tag's half-life into `decayed_weight`/`news_persistence` instead of the global default.

### L2. Underreaction to numbers vs overreaction to stories is a usable event-side split
- **Source**: `arXiv 2608.14014v1` (2026) — Buy the Rumor, Sell the News; `arXiv 2304.07619v6` (2025) — ChatGPT News.
- **Finding**: net of a background-drift placebo, quantified fundamental news (earnings, dividends, guidance, analyst actions) continues in the news direction for weeks, while story-driven news (launches, macro commentary, leadership) gives back its move; GPT-4 drift is strongest for **small stocks and negative news**.
- **Repo surface**: `tradingagents/strategies/news_score.py::corporate_events_score` (the DECLARED `FORM_EVENT_SCORES` form→event table) and `tradingagents/strategies/events.py::drift_side`.
- **Status**: `partial` — `events.drift_side` handles earnings surprise sign and PEAD, and `corporate_events_score` maps forms, but no route turns an event tag into a drift *prior* with the paper's sign.
- **Concrete step**: extend the DECLARED `FORM_EVENT_SCORES` (or add a sibling `EVENT_DRIFT_SIGN` table) with the measured +6..+20 sign per class and have the news/event renderer print "continues" vs "reverts" beside the tag, citing that it is a declared prior from an external event study, not a fitted estimate.

### L3. Attention (volume/hype) is a distinct signal from tone, and needs a size adjustment
- **Source**: `arXiv 2506.06329v1` (2025) — The Hype Index; `arXiv 1507.06477v1` (2015) — Novel and topical business news.
- **Finding**: media attention measured as a count/share is separable from tone; capitalisation-adjusted attention re-ranks names (IT drops from over-hyped to less prominent once market-cap weight is divided out), so unadjusted counts are a size proxy. Market response concentrates on novel **and** topical articles.
- **Repo surface**: `tradingagents/strategies/news_score.py::news_volume_acceleration`, `news_persistence`, `news_novelty`; `tradingagents/strategies/sentiment.py::mention_volume`, `source_breadth`.
- **Status**: `partial` — volume, novelty and source-breadth producers exist; **capitalisation-adjusted attention does not**.
- **Concrete step**: add a `cap_adjusted_hype(news_counts, market_caps)` producer (news share ÷ cap share) beside `mention_volume` and expose it as a news-score component so a hot-but-small name is not read as a large-cap-level attention event.

### L4. Novelty must be paired with topicality to be a market-relevant event
- **Source**: `arXiv 1507.06477v1` (2015) — Novel and topical business news.
- **Finding**: prices and volume respond only when an article is both novel (no similar earlier article) and topical (similar content simultaneously carried by other agencies); an unrepeated first report and a widely syndicated repeat are both weak.
- **Repo surface**: `tradingagents/strategies/news_score.py::news_novelty` (first-seen share) and `weighted_novelty` (novelty diminished by similarity).
- **Status**: `partial` — novelty exists in two forms; topicality (multi-source simultaneity) is not a component, and `weighted_novelty` moves the wrong way for this learning (it *penalises* similarity rather than rewarding consensus).
- **Concrete step**: add a `topicality(articles, window)` producer = count of distinct sources/domains carrying a similar headline in the window, and report novelty and topicality as two columns so a reader can require both.

### L5. The Loughran–McDonald dictionary runs opposite to price on filing text
- **Source**: `arXiv 2607.14174v1` (2026) — How Much of a 10-K Matters.
- **Finding**: an LM dictionary baseline is **strongly negatively correlated with price at every level tested** (sector r = −0.910; portfolio r = −0.841 to −0.937); three-fourths of Harvard-IV-4 "negative" words are not negative in a financial context, and the domain-specific list still skews negative on cautious, disclosure-mandated 10-K language. Supervised lexicon-learning beats it; Item 1A beats the full filing at firm level.
- **Repo surface**: `tradingagents/strategies/text_factors.py::lm_tone` (reduced seed, `DICTIONARY_VERSION = "lm-seed-v1"`) consumed by `tradingagents/agents/utils/quant_formula_tools.py::get_disclosure_tone`.
- **Status**: `partial` — `get_disclosure_tone` already labels the read "a deterministic second opinion" and treats zero-hits as "not neutral", but it prints a **signed** tone with no hit-rate floor and no section targeting, and a reduced seed makes low-coverage non-zero reads more likely.
- **Concrete step**: add a minimum dictionary-hit-rate (e.g. hits/words below a declared floor → withhold the sign, print counts only) and prefer Item 1A / filing text over a general news blob at firm level, matching the aggregation-level finding.

### L6. Model sentiment as a persistent episode, with asymmetric negative bursts
- **Source**: `arXiv 2607.06220v1` (2026) — Persistent Dynamics over 45 Years; `arXiv 2608.14014v1` (2026).
- **Finding**: short-scale H ≈ 0.67 (weekly-to-quarter persistence), long-scale H ≈ 0.95; daily increments are anti-persistent (H ≈ 0.43) — shocks self-correct but leave a longer residual over time; negative sentiment bursts last longer than positive ones.
- **Repo surface**: `tradingagents/strategies/sentiment.py::sentiment_dynamics` (AR(1) coefficient, lag-1 correlation) and `sentiment_asymmetry` (upside vs downside contribution).
- **Status**: `partial` — `sentiment_dynamics` gives the AR(1)/lag-1 persistence and `sentiment_asymmetry` the contribution split, but there is no **duration** asymmetry (how long a negative episode persists vs a positive one) and no multi-scale memory statistic.
- **Concrete step**: add a run-length split to `sentiment_dynamics` (mean consecutive days in a positive vs negative state) so the negative-burst asymmetry is a reported number, not an assumption.

### L7. A calibrated classifier score, not a hard label, is what a portfolio can rank
- **Source**: `arXiv 2507.18417v1` (2025) — FinDPO; `arXiv 2603.11408v2` (2026) — Beyond Polarity; `arXiv 2503.03612v4` (2025) — What is financial sentiment.
- **Finding**: DPO alignment beats SFT by 11% F1 on the same base model, but a discrete causal-LLM label cannot rank assets; a **logit-to-score conversion with temperature calibration** is required and yields Sharpe 2.0 after 5 bps costs. Multi-dimensional sentiment adds uncertainty/forwardness beyond polarity, and different models produce systematically different scores for the same text.
- **Repo surface**: `tradingagents/strategies/news_score.py::news_confidence` (sample-size/Wilson confidence) and `tradingagents/strategies/sentiment.py::sentiment_uncertainty` (entropy uncertainty over the series).
- **Status**: `absent` for an article-level finance classifier (the repo is deliberately deterministic and LLM-free on this path); `partial` for the uncertainty leg, which is series-level, not article-level.
- **Concrete step**: if any finance sentiment classifier is ever added, mandate a calibrated continuous score (temperature-scaled probability, not argmax label) and state the model/version, since the literature shows discrete labels cannot be ranked and models are not mutually reproducible; until then, keep the declared vendor scale + `normalise_sentiment` as the single source of truth.

### L8. Text-factor backtests must carry a search-size correction
- **Source**: `arXiv 2608.23808v2` (2026) — MinervaScore; and the sweep's `arXiv 2607.20093v1` (2026) — five retail signal families refuted; `arXiv 2601.06499v2` (2026) — double-selection LASSO.
- **Finding**: a Sharpe/IC selected from many trials is the maximum of those trials; deflating for the number tried (DSR) separates real edge from luck at AUROC 0.989, and the corrected DSR alone captures most of the discrimination. Text/signal-factor mining is exactly this setting.
- **Repo surface**: `tradingagents/strategies/sentiment_research.py::quintile_long_short` and `ic_term_structure`; the correction machinery already exists in `tradingagents/strategies/evaluate.py::deflated_sharpe` / `deflated_sharpe_report` (and is used by `alpha_zoo.py`, `alpha_health.py`, `trial_ledger.py`).
- **Status**: `partial` — deflation is shipped for the alpha zoo but **not wired into the sentiment-research backtests**.
- **Concrete step**: accept an `n_trials`/`trial_ledger_dir` argument in `quintile_long_short`/`ic_term_structure` and, when >1, report the deflated IC/Sharpe beside the raw one (reusing `evaluate.deflated_sharpe`) so a sentiment-factor result cannot be quoted without its search size.

### L9. Sentiment predictability is weak, regime-dependent, and decays with adoption
- **Source**: `arXiv 2304.07619v6` (2025) — Sharpe 6.54 → 1.22 as LLM adoption rose; `arXiv 2012.05906v1` (2020); `arXiv 1112.1051v1` (2011) — surveys insignificant once VIX is controlled.
- **Finding**: headline/tweet sentiment predicts returns weakly and mostly at short horizons; its signal degrades as it becomes widely used; survey sentiment is a lagging indicator that loses significance when other mood variables and VIX enter; headline sentiment shows no reliable volatility correlation.
- **Repo surface**: `tradingagents/strategies/sentiment_research.py::sentiment_factor_scale` (the overlay scale) and `rolling_information_coefficient`.
- **Status**: `partial` — the IC machinery and a bounded factor scale exist, but the scale is not tied to a measured IC half-life or an explicit decay/adoption caveat.
- **Concrete step**: have `sentiment_factor_scale` print and cap on the measured IC decay (e.g. zero the overlay when the rolling IC's sign flips or its half-life is shorter than the holding period) and attach the adoption-decay caveat to any published sentiment Sharpe.

### L10. Event-driven transcript semantics beat the hard numbers — and belong in the text layer
- **Source**: `arXiv 2203.12460v1` (2022) — Earnings Calls; `arXiv 2607.14174v1` (2026).
- **Finding**: earnings-call transcript semantics predict post-call direction more accurately than actual/estimated sales and EPS, and pre-call analyst ratings correlate weakly; disclosure-text sentiment is target-specific (return vs volatility) and section-specific.
- **Repo surface**: `tradingagents/strategies/text_factors.py::divergence` + `lm_tone`/`readability`, and the existing `tradingagents/agents/utils/analysis_tools.py::get_earnings_transcript` data path.
- **Status**: `partial` — the transcript fetch and the text-factor producers exist but are not composed: `divergence` is currently run filing-vs-news, not transcript-vs-prior-transcript.
- **Concrete step**: add a transcript read that runs `lm_tone`/`readability` on the latest vs prior quarter's transcript and reports `divergence` (tone and complexity gap) as an event signal — a deterministic composition of producers already present, feeding the PEAD path.

## 4. Where this repo is already ahead of the literature

- **Declared, multi-vendor sentiment scaling.** `sentiment_score.normalise_sentiment` + `SCALE_TABLE` pin each feed (EODHD, Alpha Vantage, GDELT −100..100) onto one canonical −1..1 unit and refuse an undeclared source. The corpus's recurring complaint (`2503.03612v4`) is that models/lexicons produce non-comparable scores with no declared unit; this repo states the unit beside every number.
- **Deterministic compute-not-narrate text layer.** The repo scores text with declared lexicons/rules rather than an LLM, avoiding the memorization/look-ahead problem the LLM-forecasting literature flags (`2304.07619v6` requires post-cutoff samples; `2605.05211v1` lists leakage as the central LLM-forecasting risk).
- **Negation handling that matches the reference index.** `sentiment.NEGATION_WINDOW = 3` with an odd/even flip rule matches the negation construction of the Shapiro et al. index described in `2607.06220v1` (multiply by −1 if negated within three words) — an independently-derived alignment, not a guess.
- **Release-time bucketing.** `sentiment._bucket_day` routes articles published after the 16:00 close to the next session, which is precisely the event-time discipline `2608.14014v1` argues the naive literature misses.
- **Refusal and coverage floors instead of neutral defaults.** `score_engine.coverage_floor`, `news_score.ABSENT_REASONS` and the "zero hits → not neutral" wording in `get_disclosure_tone` avoid the neutral-imputation error the corpus repeatedly warns about.
- **Sector/size neutralisation already shipped.** `sentiment_research.sector_neutral_z` and `residualize_sentiment` (cross-sectional OLS on log-mcap + sector dummies, winsorised) pre-empt the size/sector confound that `2506.06329v1` and `2304.07619v6` show drives raw text signals.
- **Multiple-testing tooling exists.** `evaluate.deflated_sharpe`, `pbo_flag`, CPCV, the trial ledger and the alpha zoo's deflated IC are ahead of essentially every text paper in the corpus (only `2608.23808v2` builds anything comparable). The gap is wiring (L8), not capability.
- **Syndication dedup and event tagging.** `_normalise_headline` dedup and `news_score.tag_category_read`/`corporate_events_score` already separate duplicates and event classes, the first two of `2608.14014v1`'s three missing measurement layers.

## 5. Defects or risks the literature exposes

1. **A same-day/backward correlation can be quoted as "sentiment leads."** `agents/utils/analysis_tools.py::get_sentiment_lead_lag` (the `best` loop, ~lines 11228–11235) selects the strongest |corr| across **all** lags including 0 and negative, and prints it as "strongest |corr| ... lag +0". `2608.14014v1` and `2012.05906v1` show the news-aligned move sits **at or before** publication, so a lag-0 or negative peak is the priced-in artifact, not predictability. An analyst can therefore quote a non-predictive correlation as a lead. Fix: report the strongest **positive**-lag correlation separately, or label lag ≤ 0 as "contemporaneous/priced-in".
2. **Signed LM tone with no coverage floor on filing-grade text.** `text_factors.lm_tone` (`text_factors.py:121`, reduced seed `lm-seed-v1`) surfaces through `quant_formula_tools.get_disclosure_tone` (line 430) as `tone=+X`. `2607.14174v1` shows the LM dictionary is strongly **negatively** correlated with price on 10-K text (r = −0.910 sector; −0.841..−0.937 portfolio) and that a reduced/domain list still skews negative; a low-hit non-zero tone is the failure mode. Fix: withhold the sign below a declared hit-rate floor (counts only).
3. **Novelty without topicality.** `news_score.news_novelty` (`news_score.py:331`) measures first-seen share only. `1507.06477v1` shows the significant market response requires novelty **and** topicality (simultaneous multi-agency coverage). A lone unrepeated scoop and a heavily syndicated repeat both score as weak under the current single measure, and `weighted_novelty` penalises similarity in the opposite direction to the paper's topicality effect.
4. **One global half-life for event-conditioned text.** `sentiment.decayed_weight` defaults to `half_life=7.0` (`sentiment.py:799`) and `news_score.PERSISTENCE_HALF_LIVES = (7.0, 14.0, 30.0)`. `2608.14014v1` measures materially different decay by event class (fundamental news still drifting at +20d, soft news fully reverted by +5d). A single half-life mis-times both the persistent and the reverting tails.
5. **Un-deflated sentiment-factor backtests.** `sentiment_research.quintile_long_short` / `ic_term_structure` publish IC and long-short results with no search-size deflation, while `evaluate.deflated_sharpe` and the trial ledger already exist in-repo. `2608.23808v2` (and the sweep's `2607.20093v1`) show selection inflation is the dominant failure mode in exactly this signal-mining setting; the repo's own comment (`alpha_health.py:663`) calls these rows "inputs to the DSR/PBO multiple-testing check" — the sentiment path does not yet take that step.

## 6. Limits of this review

- **Read vs skimmed.** Section 2 reports the 15 papers read in full text (abstract, method, results, limitations). Of the 46 high-relevance rows I additionally skimmed all abstracts and took the tag/method from the evidence table; the remaining 206 medium and 89 low rows were not opened individually.
- **Sampling.** The top-60 booklist supplied the deep-read pool, chosen for the emphasis themes (predictiveness, FinBERT vs general LLMs, aggregation, LM tone, attention vs tone, decay, sector/size neutralisation, event text, multiple testing). Crypto, non-US-market and pure-price-only text papers were deprioritised.
- **Not verified.** I did not run any repo test, backtest or data fetch, and did not inspect the live vendor sentiment feeds, so claims about what the repo *computes* rest on reading the module source, and claims about *what the vendors return* rest on the module docstrings only. Classifier-accuracy figures from the cs.CL papers (e.g. FinBERT/FinDPO F1, DeBERTa accuracies) are the papers' own reported numbers and were not reproduced.
- **Citation age and venue.** Several 2026 items (2608.14014, 2607.14174, 2607.06220, 2606.03457, 2608.23808, 2603.11408) are recent preprints with no peer review; the MinervaScore paper reports its own null real-market result, which I took at face value.
- **Leakage not ruled out.** For the LLM-sentiment papers I could not audit the prompt/evaluation windows; `2304.07619v6` is explicit that only post-knowledge-cutoff samples are valid, and I did not independently confirm that every cited benchmark respected its model's cutoff.
