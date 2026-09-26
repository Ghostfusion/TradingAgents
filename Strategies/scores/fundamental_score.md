Yes. For your **FundamentalScore engine**, I would treat “fundamental score” as a broad quantitative financial-health/quality/valuation framework rather than just a single Piotroski-style score.

Below is a fairly exhaustive formula library, organized so you can decide which calculations become **raw factors**, which become **subscores**, and which should remain diagnostic inputs.

## 1. Profitability

### Gross profitability

**Gross Margin**

$$
GM=\frac{Revenue-COGS}{Revenue}
$$

**Gross Profit / Assets**

$$
GP_A=\frac{Gross\ Profit}{Average\ Total\ Assets}
$$

**Gross Profit / Equity**

$$
GP_E=\frac{Gross\ Profit}{Average\ Equity}
$$

**Gross Profit Growth**

$$
GPGrowth=\frac{GP_t}{GP_{t-n}}-1
$$

**Gross Margin Change**

$$
\Delta GM=GM_t-GM_{t-1}
$$

### Operating profitability

**Operating Margin**

$$
OM=\frac{EBIT}{Revenue}
$$

**EBITDA Margin**

$$
EBITDA_M=\frac{EBITDA}{Revenue}
$$

**EBIT Margin**

$$
EBIT_M=\frac{EBIT}{Revenue}
$$

**EBIT Growth**

$$
EBITGrowth=\frac{EBIT_t}{EBIT_{t-n}}-1
$$

**EBITDA Growth**

$$
EBITDAGrowth=\frac{EBITDA_t}{EBITDA_{t-n}}-1
$$

**Operating Income Growth**

$$
OIGrowth=\frac{OI_t}{OI_{t-n}}-1
$$

**Operating Margin Change**

$$
\Delta OM=OM_t-OM_{t-1}
$$

### Net profitability

**Net Margin**

$$
NM=\frac{Net\ Income}{Revenue}
$$

**Net Income Growth**

$$
NIGrowth=\frac{NI_t}{NI_{t-n}}-1
$$

**ROA**

$$
ROA=\frac{Net\ Income}{Average\ Total\ Assets}
$$

**ROE**

$$
ROE=\frac{Net\ Income}{Average\ Shareholders'\ Equity}
$$

**ROIC**

$$
ROIC=\frac{NOPAT}{Invested\ Capital}
$$

where

$$
NOPAT=EBIT(1-TaxRate)
$$

and commonly

$$
InvestedCapital=Debt+Equity-Cash
$$

**ROCE**

$$
ROCE=\frac{EBIT}{Capital\ Employed}
$$

**ROIC − WACC**

$$
EconomicSpread=ROIC-WACC
$$

This is particularly important because a company can have a high ROIC but still destroy value if its cost of capital is higher.

---

# 2. Earnings quality

This should be a major section of your FundamentalScore because accounting earnings can diverge substantially from economic cash generation.

### Cash conversion

**CFO / Net Income**

$$
CashConversion=\frac{CFO}{NetIncome}
$$

**FCF / Net Income**

$$
FCFConversion=\frac{FCF}{NetIncome}
$$

**CFO / EBITDA**

$$
CFOConversion=\frac{CFO}{EBITDA}
$$

**CFO / Revenue**

$$
CFO_Margin=\frac{CFO}{Revenue}
$$

**FCF Margin**

$$
FCF_Margin=\frac{FCF}{Revenue}
$$

### Accruals

**Accrual Ratio**

$$
AccrualRatio=
\frac{NetIncome-CFO}{AverageTotalAssets}
$$

Lower is generally better.

Alternative:

$$
Accruals=\frac{NetIncome-CFO}{AverageAssets}
$$

### Sloan-style accrual measure

$$
SloanAccrual=
\frac{\Delta CurrentAssets-\Delta Cash-\Delta CurrentLiabilities+\Delta Debt+\Delta TaxPayables-Depreciation}
{AverageAssets}
$$

### Cash earnings

$$
CashEarnings=CFO-CapEx
$$

which is essentially FCF.

### Earnings persistence

Estimate:

$$
Earnings_t=\alpha+\beta Earnings_{t-1}+\epsilon_t
$$

The coefficient:

$$
Persistence=\beta
$$

Higher persistence indicates more persistent earnings.

### Earnings volatility

$$
EarningsVol=\sigma(ROA_t)
$$

or

$$
EarningsVol=\sigma(NI\ Growth_t)
$$

Lower volatility can be treated as higher fundamental quality.

---

# 3. Free cash flow

### Free Cash Flow

$$
FCF=CFO-CapEx
$$

### Unlevered FCF

$$
UFCF=EBIT(1-T)+D\&A-CapEx-\Delta NWC
$$

### FCF Yield

$$
FCFYield=\frac{FCF}{MarketCapitalization}
$$

### Enterprise FCF Yield

$$
EVFCFYield=\frac{FCF}{EnterpriseValue}
$$

### FCF / Sales

$$
FCFMargin=\frac{FCF}{Revenue}
$$

### FCF / Assets

$$
FCFROA=\frac{FCF}{AverageAssets}
$$

### FCF / Equity

$$
FCFROE=\frac{FCF}{AverageEquity}
$$

### FCF Growth

$$
FCFGrowth=\frac{FCF_t}{FCF_{t-n}}-1
$$

### FCF stability

$$
FCFVol=\sigma(FCFMargin)
$$

---

# 4. Growth

Fundamental scoring should distinguish **growth level** from **growth quality**.

### Revenue growth

$$
RevenueGrowth=\frac{Revenue_t}{Revenue_{t-n}}-1
$$

### CAGR

$$
CAGR=
\left(\frac{Revenue_t}{Revenue_{t-n}}\right)^{1/n}-1
$$

Do this for:

* Revenue
* Gross profit
* EBITDA
* EBIT
* EPS
* FCF
* CFO
* Book value

### EPS growth

$$
EPSGrowth=\frac{EPS_t}{EPS_{t-n}}-1
$$

### FCF growth

$$
FCFGrowth=\frac{FCF_t}{FCF_{t-n}}-1
$$

### Growth acceleration

$$
GrowthAcceleration=Growth_t-Growth_{t-1}
$$

For example:

$$
RevenueAcceleration=
RevenueGrowth_{t}-RevenueGrowth_{t-1}
$$

### Sustainable growth rate

$$
SGR=ROE\times RetentionRatio
$$

where

$$
RetentionRatio=1-DividendPayoutRatio
$$

### Internal growth rate

$$
IGR=\frac{ROA\times RetentionRatio}
{1-(ROA\times RetentionRatio)}
$$

---

# 5. Margin quality

Track both absolute margins and their direction.

### Gross margin

$$
GM=\frac{GrossProfit}{Revenue}
$$

### EBITDA margin

$$
EBITDA_M=\frac{EBITDA}{Revenue}
$$

### EBIT margin

$$
EBIT_M=\frac{EBIT}{Revenue}
$$

### Net margin

$$
NM=\frac{NetIncome}{Revenue}
$$

### FCF margin

$$
FCF_M=\frac{FCF}{Revenue}
$$

Then calculate:

$$
\Delta GM,\quad
\Delta EBITDA_M,\quad
\Delta EBIT_M,\quad
\Delta NM,\quad
\Delta FCF_M
$$

And acceleration:

$$
\Delta^2 GM=\Delta GM_t-\Delta GM_{t-1}
$$

etc.

---

# 6. Operating efficiency

### Asset turnover

$$
AssetTurnover=
\frac{Revenue}{AverageAssets}
$$

### Fixed asset turnover

$$
FixedAssetTurnover=
\frac{Revenue}{AverageNetPPE}
$$

### Working capital turnover

$$
WCturnover=\frac{Revenue}{AverageWorkingCapital}
$$

### Inventory turnover

$$
InventoryTurnover=
\frac{COGS}{AverageInventory}
$$

### Receivable turnover

$$
ARTurnover=
\frac{Revenue}{AverageAccountsReceivable}
$$

### Payables turnover

$$
APTurnover=
\frac{COGS}{AverageAccountsPayable}
$$

### Cash conversion cycle

$$
CCC=DIO+DSO-DPO
$$

where:

$$
DIO=\frac{AverageInventory}{COGS}\times365
$$

$$
DSO=\frac{AverageAR}{Revenue}\times365
$$

$$
DPO=\frac{AverageAP}{COGS}\times365
$$

Lower CCC is generally better, but sector normalization is important.

---

# 7. Working-capital quality

### Receivables growth vs revenue growth

$$
ARIntensity=\frac{AR}{Revenue}
$$

$$
\Delta ARIntensity=
ARIntensity_t-ARIntensity_{t-1}
$$

A rising AR/revenue ratio can indicate deteriorating collection quality.

### Inventory intensity

$$
InventoryIntensity=\frac{Inventory}{Revenue}
$$

### Payables intensity

$$
APIntensity=\frac{AP}{COGS}
$$

### Working capital / sales

$$
WCIntensity=\frac{NWC}{Revenue}
$$

### Change in NWC

$$
\Delta NWC=NWC_t-NWC_{t-1}
$$

---

# 8. Balance-sheet strength

### Current ratio

$$
CurrentRatio=
\frac{CurrentAssets}{CurrentLiabilities}
$$

### Quick ratio

$$
QuickRatio=
\frac{Cash+MarketableSecurities+AR}{CurrentLiabilities}
$$

### Cash ratio

$$
CashRatio=
\frac{Cash+MarketableSecurities}{CurrentLiabilities}
$$

### Net debt

$$
NetDebt=TotalDebt-Cash
$$

### Net debt / EBITDA

$$
NetDebtEBITDA=
\frac{NetDebt}{EBITDA}
$$

### Debt / EBITDA

$$
DebtEBITDA=
\frac{TotalDebt}{EBITDA}
$$

### Debt / Assets

$$
DebtAssets=
\frac{TotalDebt}{TotalAssets}
$$

### Debt / Equity

$$
DebtEquity=
\frac{TotalDebt}{Equity}
$$

### Net debt / FCF

$$
NetDebtFCF=
\frac{NetDebt}{FCF}
$$

---

# 9. Debt-service capacity

### Interest coverage

$$
InterestCoverage=
\frac{EBIT}{InterestExpense}
$$

### EBITDA interest coverage

$$
EBITDAInterestCoverage=
\frac{EBITDA}{InterestExpense}
$$

### Cash interest coverage

$$
CashInterestCoverage=
\frac{CFO}{InterestPaid}
$$

### Fixed-charge coverage

$$
FCCR=
\frac{EBIT+FixedCharges}
{FixedCharges+Interest}
$$

### Debt service coverage

$$
DSCR=
\frac{CashAvailableForDebtService}
{DebtService}
$$

---

# 10. Capital allocation

This is often overlooked in fundamental scoring.

### Dividend payout

$$
PayoutRatio=
\frac{Dividends}{NetIncome}
$$

### Retention

$$
Retention=1-PayoutRatio
$$

### Buyback yield

$$
BuybackYield=
\frac{ShareRepurchases-NetIssuance}{MarketCap}
$$

### Shareholder yield

$$
ShareholderYield=
DividendYield+BuybackYield
$$

### Total payout ratio

$$
TotalPayoutRatio=
\frac{Dividends+Buybacks}{FCF}
$$

### Reinvestment rate

$$
ReinvestmentRate=
\frac{CapEx+R\&D-\text{Depreciation}}
{NOPAT}
$$

### ROIC × reinvestment

A useful decomposition of growth:

$$
Growth_{NOPAT}\approx ROIC\times ReinvestmentRate
$$

---

# 11. Share dilution

### Shares outstanding growth

$$
ShareGrowth=
\frac{Shares_t}{Shares_{t-n}}-1
$$

### Dilution rate

$$
Dilution=
\frac{Shares_t-Shares_{t-n}}{Shares_{t-n}}
$$

### Net issuance

$$
NetIssuance=
NewShares-IssuedSharesRepurchased
$$

### Net issuance yield

$$
NetIssuanceYield=
-\frac{NetIssuance}{MarketCap}
$$

Negative net issuance means net buybacks.

---

# 12. R&D and intangible investment

Especially important for technology companies.

### R&D intensity

$$
RDIntensity=\frac{R\&D}{Revenue}
$$

### R&D growth

$$
RDGrowth=\frac{RD_t}{RD_{t-n}}-1
$$

### R&D / operating expense

$$
RDOpExRatio=
\frac{R\&D}{OperatingExpense}
$$

### R&D efficiency

$$
RDEfficiency=
\frac{\Delta GrossProfit}{R\&D}
$$

or

$$
RDEfficiency=
\frac{\Delta Revenue}{R\&D}
$$

These require careful interpretation because R&D often has a multi-year payoff period.

---

# 13. Valuation factors

Strictly speaking, valuation is sometimes separated from “fundamentals.” For your system, I'd keep it as a **Fundamental Valuation sub-engine**, not mix it blindly with financial strength.

### P/E

$$
PE=\frac{Price}{EPS}
$$

### Forward P/E

$$
ForwardPE=
\frac{Price}{ForwardEPS}
$$

### PEG

$$
PEG=
\frac{PE}{EPSGrowth}
$$

### Price / Sales

$$
PS=\frac{MarketCap}{Revenue}
$$

### Price / Book

$$
PB=\frac{MarketCap}{BookValue}
$$

### Price / FCF

$$
PFCF=\frac{MarketCap}{FCF}
$$

### EV / Revenue

$$
EVRevenue=
\frac{EnterpriseValue}{Revenue}
$$

### EV / EBITDA

$$
EVEBITDA=
\frac{EnterpriseValue}{EBITDA}
$$

### EV / EBIT

$$
EVEBIT=
\frac{EnterpriseValue}{EBIT}
$$

### EV / FCF

$$
EVFCF=
\frac{EnterpriseValue}{FCF}
$$

### Earnings yield

$$
EY=\frac{EPS}{Price}
$$

### FCF yield

$$
FCFY=\frac{FCF}{MarketCap}
$$

### Book yield

$$
BookYield=\frac{BookValue}{MarketCap}
$$

---

# 14. Earnings yield relative to bonds

A useful macro-relative valuation calculation:

$$
EYSpread=EarningsYield-RiskFreeRate
$$

Likewise:

$$
FCFYSpread=FCFYield-RiskFreeRate
$$

---

# 15. EV-based valuation

### EV

$$
EV=MarketCap+Debt+PreferredEquity+MinorityInterest-Cash
$$

### EBITDA yield

$$
EBITDAYield=\frac{EBITDA}{EV}
$$

### EBIT yield

$$
EBITYield=\frac{EBIT}{EV}
$$

### FCF yield on EV

$$
EVFCFYield=\frac{FCF}{EV}
$$

---

# 16. DuPont analysis

This is particularly useful for decomposing ROE.

$$
ROE=
NetMargin\times AssetTurnover\times EquityMultiplier
$$

where

$$
NetMargin=\frac{NI}{Revenue}
$$

$$
AssetTurnover=\frac{Revenue}{Assets}
$$

$$
EquityMultiplier=\frac{Assets}{Equity}
$$

This lets your engine distinguish:

* ROE caused by profitability
* ROE caused by asset efficiency
* ROE caused primarily by leverage

That's much more informative than treating ROE as one number.

---

# 17. Piotroski F-Score

The classic Piotroski framework contains nine binary signals. ([AAII][1])

### Profitability

$$
ROA>0
$$

$$
\Delta ROA>0
$$

$$
CFO>0
$$

$$
CFO>NI
$$

### Leverage/liquidity

$$
\Delta Leverage<0
$$

$$
\Delta CurrentRatio>0
$$

### Financing

$$
No\ new\ shares
$$

### Operating efficiency

$$
\Delta GrossMargin>0
$$

$$
\Delta AssetTurnover>0
$$

Then:

$$
FScore=\sum_{i=1}^{9}Signal_i
$$

Range:

$$
0\leq FScore\leq9
$$

This is useful as a **subscore**, rather than making it your entire FundamentalScore.

---

# 18. Beneish M-Score

This is primarily a manipulation-risk detector.

The classic model uses eight variables.

### DSRI

$$
DSRI=
\frac{Receivables_t/Sales_t}
{Receivables_{t-1}/Sales_{t-1}}
$$

### GMI

$$
GMI=
\frac{GrossMargin_{t-1}}
{GrossMargin_t}
$$

### AQI

$$
AQI=
\frac{1-(CurrentAssets+PPE)/TotalAssets_t}
{1-(CurrentAssets+PPE)/TotalAssets_{t-1}}
$$

### SGI

$$
SGI=
\frac{Sales_t}{Sales_{t-1}}
$$

### DEPI

$$
DEPI=
\frac{DepreciationRate_{t-1}}
{DepreciationRate_t}
$$

### SGAI

$$
SGAI=
\frac{SGA_t/Sales_t}
{SGA_{t-1}/Sales_{t-1}}
$$

### LVGI

$$
LVGI=
\frac{TotalDebt_t/TotalAssets_t}
{TotalDebt_{t-1}/TotalAssets_{t-1}}
$$

### TATA

$$
TATA=
\frac{IncomeFromContinuingOperations-CFO}
{TotalAssets}
$$

Then:

$$
MScore=
-4.84+
0.92DSRI+
0.528GMI+
0.404AQI+
0.892SGI+
0.115DEPI-
0.172SGAI+
4.679TATA-
0.327LVGI
$$

You can transform manipulation risk into a quality penalty rather than directly adding M-Score to quality.

---

# 19. Altman Z-Score

Useful for financial distress.

Classic formulation:

$$
Z=
1.2X_1+
1.4X_2+
3.3X_3+
0.6X_4+
1.0X_5
$$

where

$$
X_1=\frac{WorkingCapital}{TotalAssets}
$$

$$
X_2=\frac{RetainedEarnings}{TotalAssets}
$$

$$
X_3=\frac{EBIT}{TotalAssets}
$$

$$
X_4=\frac{MarketValueEquity}{TotalLiabilities}
$$

$$
X_5=\frac{Sales}{TotalAssets}
$$

For your system, this should probably feed **financial distress / risk**, rather than pure fundamental quality.

---

# 20. Ohlson O-Score

Another bankruptcy/distress model based on:

* size
* leverage
* working capital
* liquidity
* profitability
* cash flow
* earnings changes

Rather than duplicating Ohlson as a raw score, you could implement its probability output:

$$
P(Default)=\frac{1}{1+e^{-OScore}}
$$

and feed the resulting probability into the risk/quality system.

---

# 21. Quality factor calculations

You can create a composite **Quality Factor** from:

$$
Quality=
w_1ROIC+
w_2ROE+
w_3GrossProfitability+
w_4FCFQuality+
w_5EarningsStability+
w_6BalanceSheet
$$

Before aggregation, normalize each component cross-sectionally.

For example:

$$
Z_i=
\frac{X_i-\mu_{sector}}
{\sigma_{sector}}
$$

Then:

$$
QualityZ=
\sum_iw_iZ_i
$$

and transform to 0–100:

$$
Score=50+10Z
$$

with clipping:

$$
Score=\min(100,\max(0,50+10Z))
$$

---

# 22. Sector-relative normalization

This is **extremely important** for your FundamentalScore.

A raw ROIC of 15% means something very different for:

* software
* utilities
* banks
* semiconductor manufacturing
* airlines
* REITs

So instead of:

$$
Score=f(X)
$$

prefer:

$$
Score=f(X-\text{sector benchmark})
$$

or percentile:

$$
Percentile_i=
\frac{\#\{X_j<X_i\}}{N-1}
$$

Then:

$$
Score=100\times Percentile
$$

---

# 23. Robust z-score

For highly skewed financial ratios:

$$
RobustZ=
\frac{X-Median(X)}
{1.4826\times MAD}
$$

where

$$
MAD=Median(|X_i-Median(X)|)
$$

This is often better than ordinary z-scores for things like:

* P/E
* EV/EBITDA
* debt ratios
* FCF yield
* growth

---

# 24. Winsorization

Before calculating scores:

$$
X'_i=
\begin{cases}
P_1 & X_i<P_1\\
X_i & P_1\leq X_i\leq P_{99}\\
P_{99} & X_i>P_{99}
\end{cases}
$$

For many financial datasets, 2.5%/97.5% or 5%/95% winsorization can be preferable.

---

# 25. Percentile scoring

For a metric where higher is better:

$$
Score_i=100\times Percentile(X_i)
$$

For lower-is-better:

$$
Score_i=100\times(1-Percentile(X_i))
$$

Examples:

**Higher is better**

* ROIC
* FCF margin
* revenue growth
* gross margin
* interest coverage

**Lower is better**

* debt/EBITDA
* P/E
* EV/EBITDA
* accruals
* leverage
* CCC

---

# 26. Fundamental momentum

This is different from price momentum.

Calculate changes in:

$$
ROIC
$$

$$
ROE
$$

$$
GrossMargin
$$

$$
OperatingMargin
$$

$$
FCFMargin
$$

$$
AssetTurnover
$$

$$
RevenueGrowth
$$

$$
EPSGrowth
$$

Then:

$$
FundamentalMomentum=
\sum_i w_i\Delta Factor_i
$$

This is potentially very useful for your system's objective of detecting **fundamental regime changes**.

---

# 27. Fundamental acceleration

Go one step further:

$$
Acceleration_X=
(X_t-X_{t-1})-(X_{t-1}-X_{t-2})
$$

For example:

$$
ROICAcceleration=
\Delta ROIC_t-\Delta ROIC_{t-1}
$$

This can detect:

> fundamentals are not merely improving; the rate of improvement is increasing.

---

# 28. Fundamental stability

Calculate rolling volatility:

$$
\sigma_{ROIC}=
Std(ROIC_{t-k:t})
$$

$$
\sigma_{Margin}=Std(OperatingMargin_{t-k:t})
$$

$$
\sigma_{FCF}=Std(FCFMargin_{t-k:t})
$$

Then:

$$
StabilityScore=
100\times(1-NormalizedVolatility)
$$

---

# 29. Earnings surprise

If analyst estimates are available:

$$
EPSSurprise=
\frac{ActualEPS-ExpectedEPS}
{|ExpectedEPS|}
$$

Revenue surprise:

$$
RevenueSurprise=
\frac{ActualRevenue-ExpectedRevenue}
{ExpectedRevenue}
$$

Operating income surprise:

$$
EBITSurprise=
\frac{ActualEBIT-ExpectedEBIT}
{|ExpectedEBIT|}
$$

---

# 30. Estimate revision

### EPS revision

$$
EPSRevision=
\frac{CurrentEstimate-PriorEstimate}
{|PriorEstimate|}
$$

### Revenue revision

$$
RevenueRevision=
\frac{CurrentRevenueEstimate-PriorRevenueEstimate}
{|PriorRevenueEstimate|}
$$

### Forward growth revision

$$
GrowthRevision=
CurrentForwardGrowth-PriorForwardGrowth
$$

These are technically closer to **expectation/fundamental momentum** than accounting fundamentals, so I'd keep them separately identifiable.

---

# 31. Fundamental valuation gap

If you have an intrinsic value estimate:

$$
ValueGap=
\frac{IntrinsicValue-Price}{Price}
$$

or:

$$
Upside=
\frac{IntrinsicValue}{Price}-1
$$

For DCF:

$$
EV=
\sum_{t=1}^{n}\frac{FCF_t}{(1+WACC)^t}
+
\frac{TV}{(1+WACC)^n}
$$

Terminal value using perpetual growth:

$$
TV=
\frac{FCF_{n+1}}
{WACC-g}
$$

Then:

$$
EquityValue=EV-NetDebt
$$

$$
IntrinsicPrice=
\frac{EquityValue}{DilutedShares}
$$

---

# 32. Margin of safety

$$
MOS=
1-\frac{Price}{IntrinsicValue}
$$

or equivalently:

$$
MOS=\frac{IntrinsicValue-Price}{IntrinsicValue}
$$

---

# 33. Fundamental composite

For your architecture, I'd structure the FundamentalScore approximately like this:

$$
FundamentalScore=
w_P Profitability+
w_Q EarningsQuality+
w_G Growth+
w_B BalanceSheet+
w_E Efficiency+
w_C CapitalAllocation+
w_V Valuation+
w_M FundamentalMomentum
$$

For example, **illustratively**:

| Component            | Example weight |
| -------------------- | -------------: |
| Profitability        |            20% |
| Earnings quality     |            15% |
| Growth               |            15% |
| Balance sheet        |            15% |
| Operating efficiency |            10% |
| Capital allocation   |             5% |
| Valuation            |            10% |
| Fundamental momentum |            10% |
| **Total**            |       **100%** |

I would **not** hard-code these weights permanently. They should be parameters that you can backtest.

---

# 34. Hierarchical FundamentalScore

For your TradingAgents architecture, I think a hierarchical approach is much cleaner than throwing 50–100 ratios into one formula.

### Level 1 — Raw metrics

For example:

```text
ROIC
ROE
ROA
Gross Margin
EBIT Margin
FCF Margin
Revenue Growth
EPS Growth
FCF Growth
Debt/EBITDA
Interest Coverage
Current Ratio
CCC
Asset Turnover
Accrual Ratio
Share Dilution
FCF Yield
EV/EBITDA
P/E
...
```

### Level 2 — Factor scores

```text
ProfitabilityScore
GrowthScore
EarningsQualityScore
BalanceSheetScore
EfficiencyScore
CapitalAllocationScore
ValuationScore
FundamentalMomentumScore
```

### Level 3 — FundamentalScore

$$
FS=
\sum_{k=1}^{K}w_kFactorScore_k
$$

### Level 4 — Confidence

Separately calculate:

$$
Confidence=
f(
Coverage,
DataQuality,
DataFreshness,
CrossMetricAgreement,
SectorApplicability
)
$$

This is **very important for your existing scorecard architecture**.

A stock should not receive:

> FundamentalScore = 82

with the same confidence when you have 95% factor coverage versus 25%.

---

# 35. Coverage-adjusted FundamentalScore

I would explicitly separate **score** and **coverage**.

For example:

$$
Coverage=
\frac{\sum_i w_iAvailable_i}
{\sum_iw_i}
$$

Then:

$$
EffectiveScore=
Score\times Coverage
$$

But I would **not necessarily multiply the displayed FundamentalScore by coverage**, because that conflates two different concepts.

Better:

```text
FundamentalScore: 82
FundamentalCoverage: 61%
FundamentalConfidence: LOW
```

Then your existing coverage floor can decide whether the score is eligible for downstream use.

---

# 36. Cross-metric agreement

This is another useful addition for your system.

Suppose:

```text
ROIC       92
ROE        87
FCF Margin 90
Gross Prof 94
```

Strong agreement.

But:

```text
ROIC       91
ROE        89
FCF Margin 22
Accrual    15
```

There is fundamental disagreement.

You can calculate:

$$
Agreement=
1-\frac{Std(FactorScores)}{MaximumPossibleStd}
$$

or use a more robust dispersion metric.

This gives you:

```text
FundamentalScore = 78
FundamentalConfidence = 54
```

instead of pretending that the 78 is equally reliable.

---

# 37. My recommended FundamentalScore architecture for your system

Given the score architecture you've been building, I'd make the engine roughly:

```text
                         FUNDAMENTAL ENGINE
                                │
        ┌───────────────────────┼───────────────────────┐
        │                       │                       │
   Financial Quality       Financial Growth       Valuation
        │                       │                       │
   ┌────┼────┐             ┌────┼────┐           ┌────┼────┐
   │    │    │             │    │    │           │    │    │
Profit Cash Balance      Revenue EPS FCF        PE   EV   FCF
ability Flow Sheet       Growth Growth Growth        EBITDA Yield
   │    │    │             │    │    │
   └────┼────┘             └────┼────┘
        │                       │
        └───────────┬───────────┘
                    │
             Factor Normalization
                    │
          Sector / Industry Relative
                    │
              Percentile / Z
                    │
             Factor Subscores
                    │
                    ▼
             FundamentalScore
                    │
          ┌─────────┴─────────┐
          │                   │
      Coverage             Confidence
          │                   │
          └─────────┬─────────┘
                    ▼
          Fundamental Assessment
```

### The key distinction I'd make

Don't make this:

$$
FundamentalScore=
0.01X_1+0.01X_2+\cdots+0.01X_{100}
$$

That creates a huge number of highly correlated variables.

Instead:

$$
\boxed{
FundamentalScore=
\sum_{k=1}^{8}
w_k
\left(
\sum_{j=1}^{n_k}
w_{kj}Factor_{kj}
\right)
}
$$

with correlation control inside each factor group.

That lets you have **50–100 raw calculations without giving them 50–100 independent votes**.

---

## The factor library I'd actually implement

For your particular quant system, I'd start with approximately **60–80 raw calculations**, grouped into these eight families:

| Family                 | Core calculations                                                                |
| ---------------------- | -------------------------------------------------------------------------------- |
| **Profitability**      | ROIC, ROE, ROA, gross margin, EBIT margin, EBITDA margin, net margin, FCF margin |
| **Growth**             | revenue CAGR, EPS CAGR, EBIT CAGR, EBITDA CAGR, FCF CAGR, growth acceleration    |
| **Earnings Quality**   | CFO/NI, FCF/NI, accrual ratio, CFO margin, FCF stability                         |
| **Balance Sheet**      | current ratio, quick ratio, debt/assets, debt/equity, net debt/EBITDA            |
| **Debt Service**       | interest coverage, EBITDA coverage, CFO/interest, DSCR                           |
| **Efficiency**         | asset turnover, inventory turnover, DSO, DIO, DPO, CCC                           |
| **Capital Allocation** | buyback yield, dividend yield, shareholder yield, dilution, reinvestment rate    |
| **Valuation**          | P/E, EV/EBITDA, EV/EBIT, EV/Sales, P/FCF, FCF yield, earnings yield              |

Then add three **overlay subscores**:

```text
PiotroskiScore
BeneishManipulationRisk
AltmanFinancialDistress
```

And two particularly useful temporal overlays:

```text
FundamentalMomentum
FundamentalAcceleration
```

That gives you a much richer FundamentalScore than simply using conventional ratios, while keeping the architecture compatible with your existing **coverage-floor + deterministic scorecard + LLM adjudication** design. Piotroski itself is explicitly a nine-signal binary framework rather than a comprehensive fundamental model. ([AAII][1])

One other important point for your implementation: **don't combine accounting fundamentals and market-price factors indiscriminately**. In a factor-model framework, exposures and factor returns are conceptually separate from the underlying company characteristics; keeping your FundamentalScore focused on company fundamentals makes it much easier to prevent overlap with your TechnicalScore, RegimeScore, RiskScore, NewsScore, and SentimentScore. ([itsjustbeta.com][2])

[1]: https://www.aaii.com/journal/article/simple-methods-to-improve-the-piotroski-f-score?utm_source=chatgpt.com "Simple Methods to Improve the Piotroski F-Score | AAII"
[2]: https://www.itsjustbeta.com/chapters/02-the-factor-model-equation/?utm_source=chatgpt.com "The Factor Model Equation · It's Just Beta"
