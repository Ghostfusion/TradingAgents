### visbanking.com — financial-ratio-analysis-examples — https://visbanking.com/financial-ratio-analysis-examples
- **Status**: partially retrieved — page fully retrieved, but it publishes ONLY the ORIGINAL public-manufacturer Z-Score. Z'/Z'' variants are NOT present on this source (UNVERIFIED there); values below are from the fallback (Altman model literature, corroborated) and are flagged as such.

**Original Z (public manufacturers)** [https://visbanking.com/financial-ratio-analysis-examples]
- Z = 1.2A + 1.4B + 3.3C + 0.6D + 1.0E
- A = Working Capital / Total Assets
- B = Retained Earnings / Total Assets
- C = Earnings Before Interest & Taxes (EBIT) / Total Assets
- D = Market Value of Equity / Book Value of Total Liabilities
- E = Sales / Total Assets
- Zones (per source): Safe > 3.0 (low distress probability); Grey 1.8–3.0 (monitor); Distress < 1.8 (high bankruptcy probability within 2 years).
- Stated limitations: 'forward-looking', 2-year horizon; not for a single ratio; Z trend matters (example: 3.5 → 2.9 over two quarters = red flag).

**Z' (private manufacturing) — fallback, NOT on visbanking** [Altman, corroborated via https://en.wikipedia.org/wiki/Altman_Z-score and Altman (2000) search sources]
- Z' = 0.717·X1 + 0.847·X2 + 3.107·X3 + 0.420·X4 + 0.998·X5
- X1 = Working Capital/Total Assets; X2 = Retained Earnings/Total Assets; X3 = EBIT/Total Assets; X4 = **BOOK value of equity / Total Liabilities** (distinct from original's market value); X5 = Sales/Total Assets.
- Cut-offs: Safe > 2.90; Grey 1.23–2.90; Distress < 1.23.

**Z'' (non-manufacturers) — fallback**
- Z'' = 6.56·X1 + 3.26·X2 + 6.72·X3 + 1.05·X4  (X5/sales term DROPPED; X4 = book equity/TL)
- Cut-offs: Safe > 2.60; Grey 1.10–2.60; Distress < 1.10.

**Z'' (emerging markets) — fallback**
- Z'' = 3.25 + 6.56·X1 + 3.26·X2 + 6.72·X3 + 1.05·X4  (identical slopes + constant 3.25 added)
- Cut-offs: Safe > 2.60; Grey 1.10–2.60; Distress < 1.10.

**Validation evidence (Altman family)** [https://en.wikipedia.org/wiki/Altman_Z-score]
- Original estimation sample: 66 firms, 33 bankrupt (Chapter 7), all manufacturers, assets > $1m. Bankrupt-group ratio profile avg −0.25; non-bankrupt +4.48.
- Altman (1968): 72% accurate 2 years pre-bankruptcy, Type II error 6%.
- Altman (2000, 31-year re-tests): ~80–90% accurate 1 year pre-bankruptcy, Type II 15–20%.
- Explicit limitation: models NOT recommended for financial companies (opaque balance sheets, off-balance-sheet items); modern default models use market-based data.

**Aggregation/window**: point-in-time single-company score from one balance sheet + income statement (original Z uses contemporaneous market cap). No sampling/rolling rule published.
**Normalisation/weighting**: none — raw linear discriminant coefficients; no z-scoring, percentile, clipping or sector neutralisation.

**Engine-relevant notes**: Directly computable from statements the engine already pulls — Total Assets (X1,X2,X3,X5 denoms), Working Capital (X1), Retained Earnings (X2), EBIT (X3), Sales/Revenue (X5), Total Liabilities (X4 denom); Market Cap (original Z X4 numerator — engine has price×shares). For Z'/Z'' X4 use common-equity BOOK value (engine may need to derive; total equity works as proxy). MEANINGLESS for ETFs/funds and largely for banks/insurers (no retained-earnings/EBIT/working-capital economics; source itself says not for financials). Recommendation: apply original/Z'' only to non-financial operating corporates; skip funds and financials.

---

### fffinstill — Composite Scoring Methodology — https://fffinstill.com/research/methodology
- **Status**: retrieved (client-rendered page; recovered full text from embedded SSR payload) + supplementary published detail from https://fffinstill.com/blog/complete-guide-composite-health-scores-how-we-score-every-stock and https://fffinstill.com/llms-full.txt. NOTE: this is a WEIGHT-based 0–100 percentile composite, NOT a bounded point table; per-metric 'points' are NOT published.

**System A — Market Conviction Score** [methodology page]
- Market Score = (0.30 × Macro) + (0.25 × Liquidity) + (0.20 × Earnings) + (0.15 × Sentiment) + (0.10 × Insider)
- Each engine ∈ [−1,+1] with confidence ∈ [0,1]. Range clamped [−1,+1].
- Bands: Bullish +0.4..+1.0; Neutral −0.4..+0.4; Bearish −1.0..−0.4.
- Regime-adaptive modulation: when regime confidence > 0.6, weights shift ±20%. Recession Risk → ↑Liquidity,↑Sentiment / ↓Earnings,↓Insider. Early Expansion → ↑Earnings,↑Insider / ↓Macro,↓Sentiment. Mid-Cycle → base weights. Late Cycle → ↑Sentiment,↑Liquidity / ↓Earnings,↓Insider.
- Confidence = Σ(weight_i × confidence_i) × risk_adjustment; risk < −0.6 (crisis) ×0.70; risk < −0.3 (risk-off) ×0.85; else ×1.00. (Range 0..1.)
- Two non-weighted overlays (adjust confidence, not score): Risk & Volatility (30%/15% haircuts) and Sector Rotation.

**System B — Composite Health Score (0–100, sector-relative percentile)** [methodology + guide + llms-full]
- Core conversion: each of 40+ raw metrics → SECTOR percentile 0–100 in the stock's GICS sector (11 sectors; universe 2,337 stocks). Lower-is-better metrics inverted.
- Category Score = Σ(percentile × weight) ÷ Σ(weights); missing metrics excluded and remaining weights renormalised to 100%.
- Lens Score = Σ(category score × lens weight) over pillars present (same renormalisation).
- SEVEN PILLARS + weights in Overall Health: Profitability 18%, Returns 18%, Cash Flow 17%, Quality 15%, Leverage 12%, Growth Consistency 10%, Liquidity 10%.
- Metric weights within pillars:
  • Profitability: Gross Margin 1.0x; Operating Margin 1.5x; Net Margin 1.0x; Margin Stability 25% blend (8-quarter).
  • Returns: ROIC 1.5x; Incremental ROIC 1.5x; ROE 1.0x; ROA 1.0x; CROIC 1.0x. (3-yr averages blended when available.)
  • Cash Flow: FCF Margin 1.5x; OCF Margin 1.0x; OCF/Net Income 1.2x; FCF Yield 1.0x; Cash Conversion Ratio (FCF/NI) 1.2x; + overlays Capital Intensity Score and 3-Year FCF Margin Average.
  • Quality: Accruals Ratio 1.0x; Sloan Ratio 1.0x; Beneish M-Score 1.5x; Altman Z-Score 1.5x (2.0x in Safety lens); Dilution Score 1.0x; SBC/Revenue 1.3x. Min 1 metric required, else null.
  • Leverage: Net Debt/EBITDA 1.0x; Debt/Equity 1.0x; Debt/Book Assets 1.0x; Interest Coverage 1.5x; Lease-Adjusted Net Debt/EBITDA 1.0x.
  • Liquidity: Current Ratio 1.0x; Quick Ratio 1.0x; Cash Ratio 1.0x; Cash/Debt 1.0x; Working Capital % 1.0x. Min 2 metrics, else null.
  • Growth Consistency: Growth Stability (R² of revenue trend) 2.0x; 3Y Revenue CAGR 1.0x; 3Y FCF CAGR 1.5x; Margin Trend 1.0x; ROIC Trend 1.0x.
- SIX LENS SCORES (pillar weights): Overall Health = pillar weights above. Quality Focus: Cash Flow 35%, Returns 25%, Quality 25%, Profitability 15%. Safety: Leverage 40%, Liquidity 30%, Quality 30%. Capital Efficiency: Returns 45%, Cash Flow 35%, Quality 20%. Durability: Profitability 35%, Quality 35%, Growth Consistency 30%. Shareholder Value (standard): Cash Flow 40%, Quality 30%, Returns 30%; (financials): Returns 40%, Quality 20%, Cash Flow 0%.
- Shareholder-Value bonus adjustments: +5 pts if shareholder yield (dividends+buybacks−dilution) > 3%; +3 pts if low dilution AND leverage not trending up.
- Forward-looking overlays on final score (Step 4): Incremental ROIC trend ±6–8%; DOL (operating leverage) fragility ±3–10%; Refinancing Wall ±2–15%; Reinvestment Quality ±2–12%. Caps: max +12% total bonus, max −15% penalty.
- Hysteresis smoothing (Step 5): dampens small run-to-run changes (exact coefficient NOT published).
- Flags (binary, do not alter score): Dilution Tax (share count growing faster than revenue); Capex Starvation (capex below maintenance); Z-Score Exit Trigger (Z below distress threshold).
- Sector adjustments: Financials — OCF/FCF metrics excluded, ROIC→ROE, Debt/Equity, Current Ratio, Quick Ratio excluded, Interest Coverage excluded, Shareholder Value returns-only. Asset-light (Tech/Cons Disc/Comm Svcs) — Z-Score weight reduced 30–50%. Utilities/Real Estate — Z-Score not directly applicable.
- Score bands (final grade): 70–100 Elite; 60–69 Above average; 50–59 Sector median; 40–49 Below average; 20–39 Poor; <20 Distressed. Percentile caveat: 70+ strong in any sector, <30 concerning.
- **Published vs unspecified**: PUBLISHED = all pillar/lens/metric weights, percentile conversion, band table, overlay ranges+caps, sector rules, renormalisation rule. UNSPECIFIED = exact percentile interpolation method, exact per-overlay formulas, hysteresis damping coefficient, and point-accrual rules per metric (there are none — it is a weighted percentile, not a point table).
- **Validation evidence**: Universe 2,337 stocks / 11 GICS sectors. Overall Health mean 44.9, median 44.8, SD 14.0, range 14.9 (JetBlue) to 80.6; 389 stocks >60, 93 >70; distribution 40–59 43.1%, 20–39 39.4%, 60–79 16.6%, >80 1 stock. Correlations: Durability↔Overall Health 0.804; Quality Focus↔Capital Efficiency 0.965. Separately, Trajectory Conviction backtest (2018–2025): top-quintile median 52-week return +14.71% vs bottom-quintile −15.46%, spread positive in 10 of 12 periods; v2 tested on 41,392 observations across 11 sectors and 4 market-cap tiers. (Health-score IC/hit-rate NOT published.)
- **Engine-relevant notes**: Engine can reproduce almost all pillars from its inputs — Price/OHLCV (FCF Yield, market-based dilution), quarterly/annual fundamentals (margins, ROIC/ROE/ROA, FCF/OCF, leverage, liquidity, accruals, Sloan, Beneish, Altman, CAGR, R²), analyst ratings/price targets (revision-based sentiment), news relevance score (sentiment engine), options IV and FRED series (Liquidity/Volatility engine). Needs that engine lacks: GICS sector peer universe with full fundamentals for percentile ranking, GMF/FMP-style consensus estimates & realised earnings surprises, Form-4 insider and STOCK-Act congressional data, 12-quarter/8-quarter histories for trend/Sloan components. Percentile approach requires a full cross-sectional peer set, not single-name data.

---

### University of Maine System — 2020 Core Financial Ratios and Composite Financial Index — https://www.maine.edu/finance/wp-content/uploads/sites/39/2021/03/F-UMSGUS-FY20-ratios.pdf
- **Status**: retrieved (full PDF). Source textbook: *Strategic Financial Analysis for Higher Education*, 7th ed. (KPMG; Prager, Sealy & Co., LLC; ATTAIN).
- **Composite Financial Index (CFI)** answers four questions via four ratios:
  1. **Primary Reserve Ratio** = Expendable Net Position* / Total Expenses  (*excluding net position restricted for capital investments). Benchmark: 0.40x or better (≈5 months of expenses). Common Scale Value 0.133. Weight 35%.
  2. **Net Operating Revenues Ratio** = [Operating Income (Loss) + Net Non-Operating Revenues (Expenses)] / [Operating Revenues + Non-Operating Revenues]. Target 2%–4% (low 2%, high 4%). Common Scale Value 0.7%. Weight 10%.
  3. **Return on Net Position Ratio** = Change in Net Position / Total Beginning-of-Year Net Position. Benchmark 6.00% (nominal; real rate adjusts for HEPI). Common Scale Value 2.0%. Weight 20%.
  4. **Viability Ratio** = Expendable Net Position* / Long-Term Debt  (*excl. net position restricted for capital investments). 1.25 or greater = sufficient resources to satisfy debt obligations. Common Scale Value 0.417. Weight 35%.
- **Strength-factor mapping**: Strength Factor = ratio value ÷ Common Scale Value, evaluated on a common scale of **−4 to +10**, clamped (observed min −4.00, max +10.00).
- **Combination rule**: Ratio Score = Strength Factor × Weighting Factor, for each of the four ratios; **CFI = Σ of the four ratio scores**. (Weights sum to 100%: 35+10+20+35.)
- **Scale/anchor points**: CFI scale −4 to 10. 1.0 = very little financial health; 3 = low benchmark (relatively stronger position); 10 = top of the scale. Healthy region: ≥ 3 (low benchmark), high benchmark 10. Graphic profile diamonds: inner diamond = low benchmark 3; outer diamond = high benchmark 10; center = −4.
- Worked check (UMSGUS-Op FY20): PR 10.00×0.35=3.50; NOR 10.00×0.10=1.00; RONP 2.01×0.20=0.40; Viability 7.39×0.35=2.59 → CFI 7.5. ✓
- **Validation evidence**: 10 fiscal years FY11–FY20; UMSGUS/UMSGUS-Op/UMS actuals vs benchmarks (e.g., UMSGUS-Op CFI 4.7→7.5; UMS CFI 3.9→2.3; UMS falls below the 3.0 low benchmark in FY15/FY16/FY19/FY20). Stated limitation: CFI measures only the financial component; scores 'do not have absolute precision' and must be read with mission/non-financial indicators.
- **Engine-relevant notes**: This is a non-profit higher-ed model — the four component inputs (expendable net position, total expenses, operating/non-operating revenues, change in net position, long-term debt) are NOT present in the TradingAgents equity universe (no such XBRL tags for corporates; entirely inapplicable to ETFs/funds). Engineer should treat CFI as a TRANSFERABLE DESIGN PATTERN only (ratio → common-scale strength factor → fixed weights → summed index, scale −4..10, healthy ≥3), not as a runnable metric. No Z-score/Altman inputs are used here.