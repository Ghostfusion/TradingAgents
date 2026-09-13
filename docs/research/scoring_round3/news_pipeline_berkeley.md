# Scoring / Sentiment-Aggregation Research (Round 3)

### Real-Time Sentiment Analysis on Financial News: What Works and What We Deployed — https://www.lycore.com/blog/financial-news-sentiment-analysis/
- **Status**: retrieved
- **Pipeline order of operations**: (1) **Data ingestion** — direct machine-readable licensed feeds (Reuters, Bloomberg, Dow Jones Newswires; explicitly *not* web scraping), WebSocket connections to social APIs (financial Twitter/X, r/wallstreetbets, StockTwits), SEC EDGAR real-time filing feeds; dedicated ingestion servers co-located/near the feed source. Kafka for high-throughput streaming with separate consumers per source type. (2) **NLP pre-filter** — Loughran-McDonald (LM) lexicon runs FIRST: "Loughran-McDonald as a fast pre-filter for obvious positive/negative." (3) **Transformer scoring** — FinBERT served via TorchServe for "inference latency under 80ms per document." (4) **Entity extraction/asset mapping** — custom NER fine-tuned on financial entity recognition + CUSIP/ISIN mapping + proprietary ticker disambiguation lookup table maintained by the data team. (5) **Signal aggregation & noise filtering**. (6) **Storage** — TimescaleDB (time-series sentiment scores), PostgreSQL (entity mappings and source metadata). (7) **Delivery** — WebSocket push to trading systems for real-time signals; REST API for historical queries; nightly batch export to research env.
- **Formulae**: NONE stated numerically. The FinBERT+LM arrangement is described only in words: LM is a "fast pre-filter for obvious positive/negative." No lexicon-count threshold, admission rule, or rejection rule is given (i.e. the blog does NOT state how many positive/negative LM terms admit vs. route a document to FinBERT). Aggregate rules named in words only: source credibility weighting ("Reuters wire carries more signal weight than a personal blog"), velocity scoring (rate of sentiment change; neutral→strongly-negative spike > slow drift), cross-source confirmation, historical correlation.
- **Latency / throughput figures**: figure caption "from raw news feed to scored trading signal in under 100ms"; FinBERT deployed "under 80ms per document"; generic FinBERT (110M params) "50-200ms per document"; GPT-4-class "500ms-2s per document" (viable only for EOD/fundamental); scraped/RSS news lag "5-30 minutes behind the wire". No documents/sec throughput number given.
- **Aggregation / window**: real-time streaming (WebSocket); aggregation described qualitatively (source credibility, velocity, cross-source confirmation), no window length, no combine formula, no per-ticker formula.
- **Normalisation / weighting**: source-credibility weighting, velocity scoring, cross-source confirmation, historical correlation — named, not quantified.
- **Validation evidence**: production system run "across equity and forex markets for 18 months." Validation guidance: walk-forward with strict temporal separation; forward returns at 5 min / 1 hour / 1 day / 1 week; use information coefficient (IC) and rank IC rather than absolute return attribution; require p<0.05 after multiple-testing correction. No numeric IC/hit-rate reported. Stated failure modes: large-cap short-term news already priced in, raw social sentiment noise, in-sample backtests overfit ("15% annual Sharpe in backtest frequently produces near-zero or negative Sharpe live"), false positives kill trader trust (tune precision over recall on high-confidence signals; communicate confidence tiers).  
- **Engine-relevant notes (implementable)**: LM pre-filter, source-credibility weighting, velocity scoring (rate-of-change of sentiment), cross-source confirmation (count of independent sources), and time-series storage are all engine-realistic. **Required inputs the engine lacks**: the actual LM lexicon term counts and the FinBERT polarity+confidence per document (engine has relevance 0-100, not polarity). NER/CUSIP/ISIN mapping also needed for ticker attribution. The <100ms target is irrelevant to a daily engine.

---

### NLP Stock Sentiment Analysis — A Comparative Embedding-Based Model Report (Zenodo record 17510736) — https://zenodo.org/records/17510736
- **Status**: **UNVERIFIED for the Zenodo landing page itself** — zenodo.org timed out repeatedly (direct record, `/api/records/17510736`, `/export/json`, doi.org resolver, Wayback all failed). Content retrieved from the record's OWN primary documentation published by its author for the same artifact: Hugging Face model card `joyjitroy/Stock_Market_News_Sentiment_Analysis` (which states it "documents the resources and workflow described" for the Zenodo DOI), the GitHub repo `joyjitroy/Machine_Learning/NLP_Stock_Sentiment_Analysis`, and the author-hosted **Model Report PDF**. Companion dataset DOI is 10.5281/zenodo.17510735 (the 17510736 record is the model/repository artifact of the same project).
- **Aggregation period**: weekly, calendar-based. Exact code: `stock["Date"] = pd.to_datetime(stock['Date'])` then `weekly_grouped = stock.groupby(pd.Grouper(key='Date', freq='W'))` then `.agg({'News': lambda x: ' || '.join(x)})`. 18 weekly summaries.
- **Exact weighted aggregation formula**: **NONE EXISTS in this source.** Aggregation is pure concatenation of each week's headlines separated by `' || '`, then one Mistral-7B-Instruct (no fine-tuning) narrative summary per week. The HF card claims "Sentiment ratios (positive / neutral / negative) are computed" but the notebook code does not compute ratios — only concatenates. There is **no ablation of the aggregation scheme**; "sentiment-weighted or event-driven aggregation" appears only under Future Work.
- **Feature set**: text embeddings only — Word2Vec 300D (Skip-Gram trained on corpus, mean-pooled), GloVe 100D (pretrained, mean-pooled), SentenceTransformer `all-MiniLM-L6-v2` 384D (no fine-tuning). OHLCV columns exist but are explicitly EXCLUDED from the classifier features. Dataset = 349 headlines, one record per trading day.
- **Model**: Gradient Boosting Classifier; baseline default hyperparameters; tuned via `GridSearchCV(cv=5, scoring='f1_weighted')` over n_estimators, learning_rate, max_depth; 80/20 train/validation split, fixed seed.
- **COMPLETE evaluation block** (Table 3, multiclass labels {Neutral, Positive, Negative}; values as extracted):

  | Model | Set | Accuracy | Recall | Precision | F1 | Error |
  |---|---|---|---|---|---|---|
  | Word2Vec — Base | Training | 1 | 1 | 1 | 1 | 0 |
  | Word2Vec — Base | Validation | 0.381 | 0.381 | 0.381 | 0.371 | 0.667 |
  | Word2Vec — Tuned | Training | 1 | 1 | 1 | 1 | 0 |
  | Word2Vec — Tuned | Validation | 0.381 | 0.381 | 0.269 | 0.315 | 0.619 |
  | GloVe — Base | Training | 1 | 1 | 1 | 1 | 0 |
  | GloVe — Base | Validation | 0.476 | 0.476 | 0.406 | 0.438 | 0.571 |
  | GloVe — Tuned | Training | 1 | 1 | 1 | 1 | 0 |
  | GloVe — Tuned | Validation | 0.714 | 0.714 | 0.758 | 0.694 | 0.286 |

  Best model = tuned GloVe. Held-out TEST set (tuned GloVe): **accuracy 0.429, recall 0.429, precision 0.392, F1 0.388, error rate 0.619.** (SentenceTransformer rows are stated to exist in Table 3 but were not present in the extracted table.) **AUC: NOT reported anywhere (absent).** **Confusion matrix: computed and plotted** as a seaborn heatmap in the notebook (`confusion_matrix_sklearn`, labels `["Nutral", "Positive", "Negative"]`) for train/validation/test, but its numeric cells are NOT tabulated in the report text. Dataset size 349; period = "continuous date range" (one headline per trading day; no explicit start/end dates or ticker given). Metrics use `average='weighted'` for recall/precision/F1; error = `abs(target - pred)`.
- **Engine-relevant notes**: The weekly calendar rollup + concatenation is trivially adoptable, but carries no quantitative weighting. The classifier itself needs text embeddings (not adoptable without a model). The pos/neu/neg ratios require per-headline labels the engine lacks. No formula here is a candidate for the engine's aggregation; useful only as evidence that embedding-based classifiers overfit on tiny datasets (349 rows) and that validation≠test performance.

---

### Sentiment Analysis For Financial Markets (Berkeley MIDS Capstone, Fall 2024) — https://www.ischool.berkeley.edu/projects/2024/sentiment-analysis-financial-markets
- **Status**: retrieved
- **Confidence-weighted methodology**: FinBERT produces a sentiment label (positive/negative) and a confidence score per article. LSA summarises each article first (reduces noise). Per-day aggregation = **Weighted Sentiment Score**: "Positive sentiment: Add the confidence score. Negative sentiment: Subtract the confidence score." The score "captures the overall sentiment trend for each day and serves as a key feature for stock price prediction."
- **Formulae**: `WeightedSentimentScore(day d) = Σ_{articles i on d} s_i · conf_i` with `s_i = +1` if positive, `-1` if negative (neutral contributes 0). `conf_i` ∈ [0,1] is FinBERT's confidence.
- **Temporal decay**: attempted — "current date's Weighted Sentiment Score + Decayed Weighted Sentiment Score from Previous Days" — but **explicitly rejected** ("this method did not improve the model's performance either"). No decay constant / half-life / exact formula is stated. Also: `combined_score = (#positive) − (#negative)` (unweighted count variant, from linked repo) was tried; counts + average confidence per label also tried and rejected.
- **Relevance / source trust**: NOT part of the formula. No source-trust term, no article-relevance term.
- **Model / features**: ARIMA(p,d,q) on stock return `(close − open)/open`; feature X = {Date, Open, Volume, Weighted Sentiment Score}; sentiment score is "the most influential variable"; p,d,q tuned. RMSE primary metric; baseline = same models with sentiment feature removed; most models beat baseline.
- **Results**: no numeric RMSE given; "predicted stock prices showed strong overlap with actual"; a portfolio of high-sentiment stocks "yielded a higher return compared to the S&P 500 index."
- **Justification for weighting vs simple averaging**: not argued theoretically; empirically they tried mode+avg-confidence and counts+average and found no benefit, so kept the simple signed-confidence sum. Users found the numeric score confusing, so the UI was changed to plain positive/negative/neutral labels.
- **Engine-relevant notes**: the `Σ s_i·conf_i` aggregation is directly implementable IF per-article signed polarity and confidence exist. Engine instead stores relevance 0-100 (unsigned), so this cannot be built today.

---

### Sentiment Analysis for Financial Markets (slide PDF) — https://www.ischool.berkeley.edu/sites/default/files/sentiment-analysis-for-financial-markets.pdf
- **Status**: retrieved
- **Exact Weighted Sentiment Score pseudocode (slide 16)**:
  - `If sentiment_label == "positive": weighted_score += confidence_score`
  - `If sentiment_label == "negative": weighted_score -= confidence_score`
  - (neutral: no change -> contributes 0)
- **Attempt history (slide 17)**: Attempt 1 = Sentiment Score: Mode, Confidence Score: Avg of Mode; Attempt 2 = Sentiment Score: Label Count, Confidence: Average of Each Label; Attempt 3 = Weighted Sentiment Score; Attempt 4 = Current Date's Weighted Sentiment Score + Decayed Weighted Sentiment Score from Previous Days (rejected). So the FINAL deployed aggregation is Attempt 3 (signed confidence sum); decay term was abandoned.
- **Model (slide 14-15)**: ARIMA; hyperparameters p (past values), d (differencing to stationarity), q (lagged forecast errors); Y = return, X = {Date, Open, Volume, Weighted Sentiment Score}. Other models explored: Linear Regression, Random Forest, XGBoost.
- **Recommendation pipeline (slides 20-21)**: real-time news + real-time stock -> pre-trained model -> predicted return; combine with "Professional Opinion" -> convert predicted return + convert professional opinion -> calculate combined score -> convert to recommendation (buy/hold/sell).
- **Limitations (slide 22)**: historical datasets lack latest data; dataset dates may not match actual news-event dates; real-time news API retrieves irrelevant news for non-relevant stocks.
- **Engine-relevant notes**: same as source 3. The only concrete formula in this whole round is `Σ s_i·conf_i` (sign·confidence), neutral = 0. No relevance weighting, no source weighting, no decay (abandoned).

---

## Cross-source synthesis for the engine
- **Only exact formula found this round**: Berkeley `WeightedSentimentScore = Σ_i s_i · conf_i`, `s_i ∈ {+1,0,-1}`, `conf_i = FinBERT confidence ∈ [0,1]`; unweighted variant `Σ s_i`. Lycore's weights are qualitative; Roy's "weekly rollup" has no formula (concatenation only).
- **No source provides an article-relevance term or a source-trust coefficient inside the aggregation formula.** Lycore names source credibility as a concept but never quantifies it.
- **What a confidence-weighted aggregation needs that the engine does not store**: (1) per-article SIGNED sentiment polarity (+1/0/−1); (2) per-article model CONFIDENCE (0-1) — engine's relevance 0-100 is a different construct and is unsigned; (3) a source→trust-weight map (sources are stored, but no trust weights); (4) decay parameters (λ / half-life) if temporal decay is added — engine stores timestamps, so decay is feasible once λ is defined; (5) ticker/entity mapping for per-ticker rollup.
- **Adoptable without a transformer**: Berkeley signed-confidence aggregation (once polarity+confidence are captured), Lycore source-credibility weighting and velocity scoring and cross-source confirmation, and calendar-based weekly rollup (Roy style) as a reporting layer. Not adoptable without a model: FinBERT/embedding classification and LM-lexicon pre-filter (both need a lexicon/model plus per-document polarity).
