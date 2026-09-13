### MSCI Analyst Sentiment Indexes — Methodology (April 2025)
URL: https://www.msci.com/documents/10199/a925c038-cf5e-9701-fe7a-e4414a06b1ca
- Status: retrieved (full 16-page PDF; no performance/validation section).
- Underlying analyst data: five descriptor groups from MSCI FactorLab — Cash flow per share (CPS), EPS, Sales (SALES), Analyst Recommendation (REC), Price Target (PRICE TGT).
- Exact score: AS_i = Average(CPS_i, EPS_i, SALES_i, REC_i, PRICE TGT_i); then winsorized z-score (at +/-3) of that average. Descriptor group score = winsorized (+/-3) z-score of the average of that group's descriptors (e.g. CPS group = winsor-z of avg(CPS_RR_SLOW, CPSF_C, CPSTOPF_C)). [sec 2.2, Appendix I]
- Revision ratio: EPSRR(t) = SUM_{l=0,1,2} w_{t,-l} * (N^up_{t-l*21} - N^down_{t-l*21}) / N^total_{t-l*21}, weights {3,2,1}; 21 = trading days/month; mid-month date uses pro-rated latest partial month. Analogues: CPS_RR_SLOW, SALTOP_RR_SLOW, PTG_RR_SLOW, REC_RR_SLOW.
- Change in estimate: EPSFC(t) = SUM_{l=0,1,2,3} w_l * (EPSF_{t-l*63} - EPSF_{t-(l+1)*63}) / ((|EPSF_{t-l*63}|+|EPSF_{t-(l+1)*63}|)/2), weights {9,7,5,3}; 63 = trading days/quarter. Analogue: CPSF_C, SALF_C, PTGF_C, RECF_C. Estimate-to-market: ETOPFC same form, weights {9,7,5,3}; analogues CPSTOPF_C, SALTOPF_C (SALES/market cap).
- Coverage rule: only groups covered by >1 analyst count; missing groups -> average available; minimum one group required.
- Normalisation: cross-sectional winsorized z-scores (+/-3) vs parent universe.
- Rebalancing: quarterly, close of last business day of Feb/May/Aug/Nov (aligned to GIMI reviews); inputs as of day before rebalancing; pro forma announced ~9 business days ahead; one-way turnover cap 20%.
- Universe: Parent = free-float market-cap weighted MSCI index (GIMI); eligible = parent constituents with an AS score; no shorting; default USD.
- Tradeable signal: Barra Open Optimizer + GEMLTL; maximise AS score less active-risk penalty. Constraints: Large Cap weight in [max(parent-2%,0), min(parent+2%,10x parent)]; Mid/Small Cap [max(parent-1%,0), min(parent+1%,5x parent)]; Momentum active exposure > +0.1 sd; 15 other Barra styles within +/-0.1 sd; factor/specific risk aversion 0.01; ex-ante TE cap 4%; active specific risk cap 2%; beta 0.98–1.02; GICS sector +/-5%; country >2.5% -> +/-5%, <=2.5% -> 3x cap; China A Stock Connect separate group. Infeasible: relax weight multiple +2x/+1x (to 20x/10x), turnover to 30%, TE to 5%, specific risk to 2.5%; else no rebalance.
- Validation: NONE stated (no IC/hit-rate/alpha).
- Engine: {3,2,1} and {9,7,5,3} weights, winsor-z, coverage rule, quarterly rebalance all implementable from an analyst ratings feed. MISSING: per-descriptor up/down/total revision counts, EPS/CPS/SALES/price-target estimate levels over 3–4 quarters, analyst coverage counts, Barra factor covariance.

### TradingSim — Bull/Bear Ratio (Al Hill; upd. 2026-05-23)
URL: https://www.tradingsim.com/blog/bull-bear-ratio
- Status: retrieved.
- Definition: weekly Investor Intelligence survey of >100 investment newsletter writers/editors (bullish / bearish / neutral on US equities); released every Wednesday.
- Exact formula: (Number of Bullish views / (Bullish + Bearish views)) x 100. Neutrals EXCLUDED from denominator. Example: 45 bull, 30 bear, 25 neutral -> 45/75 x 100 = 60%.
- Bands: crowded bullish above 60%, crowded bearish below 40%; chart oscillator at 0.60/0.40.
- Usage: contrarian at extremes (optimism -> correction risk; pessimism -> bounce); rising 5–10 weeks = rising optimism; weekly -> swing not day trading. Cross-refs: sub-40% bull/bear + VIX >30 = capitulation tell; put/call extremes; AAII retail survey.
- Limitations: weekly only; herds stay wrong for months (extremes persist); ignores algo/CTA/passive flows; respondents game the survey; use only alongside other inputs.
- Validation: none (no hit rate/backtest).
- Engine: formula + 40/60 bands trivially implementable, but engine ingests NO advisor survey. Prediction-market probability (binary P(yes)) is the closest crowd-poll substitute for the bullish share.

### FMP — Social Sentiment Indicator guide (Parth Sanghvi; upd. 2026-03-31)
URL: https://site.financialmodelingprep.com/education/other/social-sentiment-indicator--indepth-guide-to-analyzing-market-sentiment
- Status: retrieved (conceptual; NO numeric weights, NO buzz×polarity formula).
- Stated weighting factors (no relative weights): (a) source credibility, (b) volume of mentions, (c) context in which the company is discussed.
- Pipeline: collect continuously from social (Twitter, Facebook), news, blogs, forums; NLP classifies text positive/negative/neutral; apply the 3 factors; aggregate per ticker; analyse history for trends/spikes.
- Scoring rule: "Assign sentiment scores (e.g., +1 for positive, -1 for negative) to each data point and aggregate these scores to form an overall sentiment index."
- Normalisation: lowercasing/punctuation removal before scoring; spam filtering; no z-score/percentile method stated.
- Validation: none. Engine: credibility ~ outlet tier (not ingested), volume ~ article count per ticker/day (computable), context ~ per-article relevance score 0–100. Polarity needs an NLP model the engine lacks; social feeds not ingested.

### Adanos — X/Twitter Stock Sentiment API + Buzz Score whitepaper
URLs: https://adanos.org/x-stock-sentiment ; https://adanos.org/buzzscore-whitepaper.pdf
- Status: retrieved (API page + 12-page empirical whitepaper).
- Pipeline: Grok flags trending cashtags on X, million real tweets/replies via twscrape; 35,000+ tickers; hourly refresh; default 7-day lookback.
- VADER + RoBERTa split: hybrid VADER + Twitter-RoBERTa; VADER enhanced with finance lexicon (moon, tendies, bearish, short squeeze) and emoji (rocket, bear, diamond-hands); whitepaper gives ensemble weights RoBERTa 60% / VADER 40% (VADER + 150+ finance terms), refined by phrase/emoji signals. Score range -1.0 (bearish) to +1.0 (bullish). Non-English usually skipped.
- Buzz score (0–100), five weighted factors: mentions (20), sentiment (20), quality (10), author diversity (14, HHI-based), trend (-10 to +20); above 50 asymptotic scaling. Component construction: log10(mentions+1)x20; ensemble sentiment (-1..+1)x20; log10(upvotes/mention+1)x10 (volume-scaled); log10(effective communities+1)x14 with effective = 1/HHI; trend -10..+20 (recent vs older mentions, asymmetric caps). Bands: 0–20 minimal, 40–60 active, 80+ exceptional.
- Window/aggregation: trend = current 3 UTC days vs previous 3 UTC days (rising >+10%, falling <-10%, stable +/-10%); trend_history = 7 daily buzz scores; replies inherit context at 0.1 weight one level deep; author guard caps single-account contributions.
- Validation (whitepaper, Reddit feed): 198 S&P 500 names, 11 sectors, ~249 sessions, 49,313 ticker-days, 2025-06-12 to 2026-06-10. Buzz↔log volume r=+0.24 (t 18.4, 92% of names); Buzz↔|return| r=+0.16 (t 17.6, 88%); sentiment↔return r=+0.08; Buzz(t-1) predicts next-day volatility r=+0.09 (t 12.6, 79%); sentiment does NOT predict sign (r=-0.00). 1,011 spikes: volume 1.9x median, volatility +87% (3.3% vs 1.8%). Sector +0.27 IT to -0.06 Real Estate. Limitation: magnitude not sign; one-year sample.
- Engine: sentiment/vader-roberta require X text + models the engine lacks. Buzz skeleton maps onto news feed: mentions->article count, quality->relevance/100, sentiment->headline polarity or prediction-market prob, diversity->1/HHI over outlets, trend->3d vs prior-3d change, then log10 + asymptotic-to-100 scaling.