Absolutely. If you are designing a **quantitative stock-analysis system**, the market-research phase should ideally calculate much more than just technical indicators. I would organize the calculations into **12 major research layers**.

Below is a comprehensive formula inventory you can use as a checklist for your quant system.

---

# Quant Market-Research Calculations & Formulas

## 1. Price & Return Calculations

These are the foundation for virtually every other calculation.

### Basic price changes

**Absolute change**

$$
\Delta P_t=P_t-P_{t-1}
$$

**Percentage change**

$$
R_t=\frac{P_t-P_{t-1}}{P_{t-1}}
$$

**Log return**

$$
r_t=\ln\left(\frac{P_t}{P_{t-1}}\right)
$$

**Cumulative return**

$$
R_{cum}=\frac{P_t}{P_0}-1
$$

**Annualized return**

$$
R_{ann}=\left(\frac{P_t}{P_0}\right)^{252/N}-1
$$

### Multi-period returns

$$
R_n=\frac{P_t}{P_{t-n}}-1
$$

Typical research windows:

* 1D
* 5D
* 10D
* 20D
* 1M
* 3M
* 6M
* YTD
* 1Y
* 3Y
* 5Y

---

# 2. OHLC / Price-Structure Calculations

### Daily range

$$
Range_t=H_t-L_t
$$

### Percentage range

$$
Range\%=\frac{H_t-L_t}{C_t}
$$

### True Range

$$
TR_t=\max
\begin{cases}
H_t-L_t\\
|H_t-C_{t-1}|\\
|L_t-C_{t-1}|
\end{cases}
$$

### Typical price

$$
TP_t=\frac{H_t+L_t+C_t}{3}
$$

### Median price

$$
MP_t=\frac{H_t+L_t}{2}
$$

### OHLC4

$$
OHLC4=\frac{O_t+H_t+L_t+C_t}{4}
$$

### Candle body

$$
Body=|C-O|
$$

### Upper wick

$$
UpperWick=H-\max(O,C)
$$

### Lower wick

$$
LowerWick=\min(O,C)-L
$$

### Body/range ratio

$$
BodyRatio=\frac{|C-O|}{H-L}
$$

These are useful for identifying:

* momentum candles
* indecision
* rejection
* breakout candles
* reversal candles

---

# 3. Moving-Average Calculations

## Simple Moving Average

$$
SMA_n=\frac{1}{n}\sum_{i=0}^{n-1}P_{t-i}
$$

Common:

* SMA 5
* SMA 10
* SMA 20
* SMA 50
* SMA 100
* SMA 200

## EMA

$$
EMA_t=\alpha P_t+(1-\alpha)EMA_{t-1}
$$

where

$$
\alpha=\frac{2}{n+1}
$$

Common:

* EMA 9
* EMA 12
* EMA 20
* EMA 21
* EMA 26
* EMA 50
* EMA 100
* EMA 200

### Price distance from MA

$$
Distance\%=\frac{P-SMA_n}{SMA_n}\times100
$$

### MA slope

$$
Slope=\frac{MA_t-MA_{t-k}}{k}
$$

### MA slope percentage

$$
Slope\%=\frac{MA_t-MA_{t-k}}{MA_{t-k}}\times100
$$

---

# 4. Volatility Calculations

This is one of the most important research categories.

## Standard deviation

$$
\sigma=\sqrt{\frac{1}{n-1}\sum_{i=1}^{n}(r_i-\bar r)^2}
$$

### Annualized volatility

$$
\sigma_{ann}=\sigma_{daily}\sqrt{252}
$$

### Downside volatility

$$
\sigma_{down}=
\sqrt{\frac{1}{n-1}
\sum \min(r_i,0)^2}
$$

### Historical volatility

Usually:

$$
HV=\operatorname{StdDev}(\ln(P_t/P_{t-1}))\sqrt{252}
$$

---

# 5. ATR Calculations

## ATR

$$
ATR_n=SMA_n(TR)
$$

or Wilder's smoothing.

### ATR percentage

$$
ATR\%=\frac{ATR}{Price}\times100
$$

### ATR expansion

$$
ATRExpansion=
\frac{ATR_n}{ATR_{n,k}}-1
$$

Useful for detecting:

* volatility expansion
* volatility contraction
* breakout conditions
* "knife" conditions
* abnormal risk

---

# 6. Bollinger Band Calculations

Given:

$$
Middle=SMA_n
$$

$$
Upper=Middle+k\sigma
$$

$$
Lower=Middle-k\sigma
$$

### Bandwidth

$$
BBWidth=
\frac{Upper-Lower}{Middle}
$$

### Bandwidth percentage

$$
BBWidth\%=BBWidth\times100
$$

### %B

$$
\%B=
\frac{Price-Lower}{Upper-Lower}
$$

Interpretation:

* < 0 → below lower band
* 0 → lower band
* 0.5 → middle
* 1 → upper
* > 1 → above upper

### Bandwidth percentile

$$
BBPercentile=
PercentileRank(BBWidth_t,N)
$$

Extremely useful for detecting **squeeze → expansion**.

---

# 7. Momentum Calculations

## Rate of Change

$$
ROC_n=
\frac{P_t-P_{t-n}}{P_{t-n}}\times100
$$

## Momentum

$$
Momentum_n=P_t-P_{t-n}
$$

## RSI

$$
RS=\frac{AverageGain}{AverageLoss}
$$

$$
RSI=100-\frac{100}{1+RS}
$$

Common periods:

* RSI 7
* RSI 14
* RSI 21

### RSI slope

$$
RSISlope=RSI_t-RSI_{t-k}
$$

### RSI acceleration

$$
RSIAccel=(RSI_t-RSI_{t-1})-(RSI_{t-1}-RSI_{t-2})
$$

---

# 8. Stochastic Calculations

### %K

$$
\%K=
100\times
\frac{C-L_n}{H_n-L_n}
$$

### %D

$$
\%D=SMA_m(\%K)
$$

Useful calculations:

* %K
* %D
* K-D spread
* K slope
* D slope
* oversold/overbought duration

---

# 9. MACD Calculations

$$
MACD=EMA_{12}-EMA_{26}
$$

### Signal

$$
Signal=EMA_9(MACD)
$$

### Histogram

$$
Histogram=MACD-Signal
$$

### Histogram slope

$$
HistSlope=Hist_t-Hist_{t-1}
$$

### Histogram acceleration

$$
HistAccel=HistSlope_t-HistSlope_{t-1}
$$

This is particularly useful for detecting **momentum weakening before a crossover**.

---

# 10. Trend Calculations

### Trend strength

One simple measure:

$$
TrendStrength=
\frac{MA_{short}-MA_{long}}{MA_{long}}
$$

### Price vs 200 SMA

$$
P200Distance=
\frac{P-SMA_{200}}{SMA_{200}}
$$

### Golden cross

$$
SMA_{50}>SMA_{200}
$$

### Death cross

$$
SMA_{50}<SMA_{200}
$$

### MA alignment

Bullish example:

$$
EMA_20>EMA_{50}>EMA_{200}
$$

Bearish:

$$
EMA_{20}<EMA_{50}<EMA_{200}
$$

### Trend persistence

$$
TrendPersistence=
\frac{\#\{days:P_t>SMA_n\}}{N}
$$

This can be much more informative than simply saying "above SMA."

---

# 11. ADX / Directional Movement

### Positive directional movement

$$
+DM_t=
\begin{cases}
H_t-H_{t-1}, & \text{if positive and greater than downward movement}\\
0,&otherwise
\end{cases}
$$

### Negative directional movement

Analogous:

$$
-DM_t
$$

### Directional indicators

$$
+DI=100\times\frac{Smoothed(+DM)}{ATR}
$$

$$
-DI=100\times\frac{Smoothed(-DM)}{ATR}
$$

### DX

$$
DX=
100\times
\frac{|+DI--DI|}{+DI+-DI}
$$

### ADX

$$
ADX=Smoothing(DX)
$$

Research signals:

* ADX level
* ADX slope
* +DI/-DI crossover
* directional dominance

---

# 12. Volume Calculations

Volume deserves its own research layer.

### Volume SMA

$$
VolMA_n=SMA_n(Volume)
$$

### Relative volume

$$
RVOL=
\frac{Volume_t}{AverageVolume_n}
$$

### Volume anomaly

$$
VolumeZ=
\frac{Volume-\mu_{Volume}}{\sigma_{Volume}}
$$

### Volume percentage change

$$
VolumeChange\%=
\frac{V_t-V_{t-1}}{V_{t-1}}\times100
$$

### Dollar volume

$$
DollarVolume=P\times Volume
$$

### Average dollar volume

$$
ADV_n=SMA_n(DollarVolume)
$$

---

# 13. OBV Calculations

On-Balance Volume:

$$
OBV_t=
\begin{cases}
OBV_{t-1}+V_t,&C_t>C_{t-1}\\
OBV_{t-1}-V_t,&C_t<C_{t-1}\\
OBV_{t-1},&otherwise
\end{cases}
$$

Then calculate:

* OBV slope
* OBV moving average
* price/OBV divergence
* OBV breakout

---

# 14. VWAP Calculations

### VWAP

$$
VWAP=
\frac{\sum TP_iV_i}{\sum V_i}
$$

### Price distance from VWAP

$$
VWAPDistance\%=
\frac{P-VWAP}{VWAP}\times100
$$

### VWAP deviation

$$
VWAPDeviation=
\frac{P-VWAP}{\sigma_{VWAP}}
$$

---

# 15. Support / Resistance Calculations

### Rolling high

$$
Resistance_n=\max(H_{t-n+1},...,H_t)
$$

### Rolling low

$$
Support_n=\min(L_{t-n+1},...,L_t)
$$

### Distance to resistance

$$
DistResistance=
\frac{Resistance-P}{P}
$$

### Distance to support

$$
DistSupport=
\frac{P-Support}{P}
$$

### Pivot point

$$
PP=\frac{H+L+C}{3}
$$

$$
R1=2PP-L
$$

$$
S1=2PP-H
$$

$$
R2=PP+(H-L)
$$

$$
S2=PP-(H-L)
$$

---

# 16. Drawdown Calculations

### Running peak

$$
Peak_t=\max(P_0,...,P_t)
$$

### Drawdown

$$
DD_t=\frac{P_t-Peak_t}{Peak_t}
$$

### Maximum drawdown

$$
MDD=\min(DD_t)
$$

### Recovery

$$
Recovery=
\frac{P_t-Trough}{Peak-Trough}
$$

Useful for measuring:

* crash risk
* recovery strength
* historical downside
* risk regime

---

# 17. Risk-Adjusted Return Calculations

## Sharpe ratio

$$
Sharpe=
\frac{R_p-R_f}{\sigma_p}
$$

Annualized:

$$
Sharpe_{ann}=
\frac{\bar R_p-R_f}{\sigma_p}\sqrt{252}
$$

## Sortino ratio

$$
Sortino=
\frac{R_p-R_f}{\sigma_{down}}
$$

## Calmar ratio

$$
Calmar=
\frac{AnnualizedReturn}{|MDD|}
$$

---

# 18. Distribution / Statistical Calculations

### Mean

$$
\mu=\frac{1}{N}\sum x_i
$$

### Median

$$
Median(x)
$$

### Variance

$$
\sigma^2=
\frac{1}{N-1}\sum(x_i-\bar{x})^2
$$

### Standard deviation

$$
\sigma=\sqrt{\sigma^2}
$$

### Z-score

$$
Z=\frac{x-\mu}{\sigma}
$$

### Percentile rank

$$
PR(x)=\frac{\#(x_i\le x)}{N}
$$

### Skewness

$$
Skew=
\frac{E[(X-\mu)^3]}{\sigma^3}
$$

### Kurtosis

$$
Kurt=
\frac{E[(X-\mu)^4]}{\sigma^4}
$$

These become useful for identifying **non-normal return distributions and tail risk**.

---

# 19. Correlation Calculations

### Pearson correlation

$$
\rho_{XY}=
\frac{Cov(X,Y)}
{\sigma_X\sigma_Y}
$$

Calculate correlation between:

* stock vs SPY
* stock vs QQQ
* stock vs sector ETF
* stock vs industry peers
* stock vs VIX
* stock vs Treasury yields
* stock vs commodities
* stock vs dollar

### Rolling correlation

$$
\rho_t=
Corr(X_{t-n:t},Y_{t-n:t})
$$

The **change in correlation regime** can be more valuable than the raw correlation.

---

# 20. Beta Calculations

### Market beta

$$
\beta=
\frac{Cov(R_i,R_m)}
{Var(R_m)}
$$

### Rolling beta

$$
\beta_t=
\frac{Cov(R_{i,t-n:t},R_{m,t-n:t})}
{Var(R_{m,t-n:t})}
$$

### Alpha

$$
\alpha=R_i-[R_f+\beta(R_m-R_f)]
$$

---

# 21. Relative Strength Calculations

### Relative strength vs benchmark

$$
RS=
\frac{P_{stock}}{P_{benchmark}}
$$

### RS return

$$
RSReturn=
\frac{RS_t}{RS_{t-n}}-1
$$

For example:

$$
RS_{QQQ}=\frac{StockPrice}{QQQPrice}
$$

Also calculate:

* stock vs SPY
* stock vs QQQ
* stock vs sector ETF
* stock vs industry ETF

---

# 22. Sector / Industry Relative Performance

### Sector excess return

$$
SectorExcess=
R_{sector}-R_{SPY}
$$

### Stock excess return

$$
StockExcess=
R_{stock}-R_{sector}
$$

This lets you distinguish:

> "The stock is going up because the whole sector is going up"

from:

> "The stock is actually outperforming its sector."

---

# 23. Market Regime Calculations

A serious quant research system should calculate regime variables.

### Market trend

$$
SPY>SMA_{200}
$$

### Volatility regime

$$
VIX>VIX_{threshold}
$$

### Volatility percentile

$$
VIXPercentile=
PercentileRank(VIX,N)
$$

### Volatility change

$$
\Delta VIX=
\frac{VIX_t}{VIX_{t-n}}-1
$$

### Market breadth

$$
Breadth=
\frac{\#AdvancingStocks}
{\#AdvancingStocks+\#DecliningStocks}
$$

### Advance/decline ratio

$$
ADRatio=
\frac{Advancers}{Decliners}
$$

### Advance/decline line

$$
ADLine_t=ADLine_{t-1}+Advancers-Decliners
$$

---

# 24. Breadth Calculations

Particularly useful for market research.

### % above SMA

$$
PctAboveMA=
\frac{\#Stocks(P>SMA_n)}
{TotalStocks}\times100
$$

Calculate for:

* SMA20
* SMA50
* SMA200

### New highs / new lows

$$
NHNL=NewHighs-NewLows
$$

### McClellan-type measures

Using advances and declines:

$$
Oscillator=EMA_{19}(AD)-EMA_{39}(AD)
$$

---

# 25. Gap Calculations

### Gap %

$$
Gap\%=
\frac{Open-C_{prev}}{C_{prev}}\times100
$$

### Gap up

$$
Open>C_{prev}
$$

### Gap down

$$
Open<C_{prev}
$$

### Gap fill

For an upside gap:

$$
GapFill=
\frac{C_{prev}-Low}{Open-C_{prev}}
$$

Useful for studying:

* earnings gaps
* breakouts
* exhaustion gaps
* gap continuation
* gap fills

---

# 26. Breakout Calculations

### High breakout

$$
P_t>\max(H_{t-n:t-1})
$$

### Low breakdown

$$
P_t<\min(L_{t-n:t-1})
$$

### Breakout distance

$$
BreakoutStrength=
\frac{P_t-Resistance}{ATR}
$$

### Volume-confirmed breakout

$$
RVOL>Threshold
$$

combined with:

$$
P>Resistance
$$

---

# 27. Mean-Reversion Calculations

### Distance from mean

$$
Deviation=
\frac{P-MA}{MA}
$$

### Z-score

$$
Z=\frac{P-MA}{StdDev}
$$

### Mean-reversion signal

Example:

$$
Z<-2
$$

followed by:

$$
Z_t>Z_{t-1}
$$

This is particularly useful for your **MR regime/gate architecture**.

---

# 28. Momentum Regime Calculations

A useful composite:

$$
MomentumScore=
w_1ROC_{20}
+w_2ROC_{60}
+w_3ROC_{120}
$$

Normalize each component first.

Possible components:

* ROC
* RSI
* MACD histogram
* price vs EMA
* relative strength
* volume confirmation

---

# 29. Volatility-Regime Calculations

Example:

$$
VolRatio=
\frac{ATR_{20}}{ATR_{100}}
$$

Interpretation:

* < 1 → compressed volatility
* ≈ 1 → normal
* > 1 → expanding volatility

Another:

$$
VolZ=
\frac{\sigma_{20}-\mu_{\sigma}}{\sigma_{\sigma}}
$$

---

# 30. Liquidity Calculations

### Average daily volume

$$
ADV_n=SMA_n(Volume)
$$

### Average dollar volume

$$
ADVol_n=SMA_n(P\times Volume)
$$

### Volume/float

$$
Turnover=
\frac{Volume}{Float}
$$

### Average turnover

$$
AvgTurnover=SMA_n(Turnover)
$$

These are important before allowing a stock into a trading universe.

---

# 31. Market-Cap / Fundamental Quant Calculations

For equity research, technical calculations alone aren't enough.

### Market capitalization

$$
MarketCap=Price\times SharesOutstanding
$$

### Enterprise value

$$
EV=MarketCap+Debt+PreferredStock+MinorityInterest-Cash
$$

### EV/Sales

$$
EV/Sales=\frac{EV}{Revenue}
$$

### EV/EBITDA

$$
EV/EBITDA=\frac{EV}{EBITDA}
$$

### P/E

$$
P/E=\frac{MarketCap}{NetIncome}
$$

or

$$
P/E=\frac{Price}{EPS}
$$

### PEG

$$
PEG=\frac{P/E}{EPSGrowth}
$$

---

# 32. Profitability Calculations

### Gross margin

$$
GrossMargin=
\frac{Revenue-COGS}{Revenue}
$$

### Operating margin

$$
OperatingMargin=
\frac{OperatingIncome}{Revenue}
$$

### Net margin

$$
NetMargin=
\frac{NetIncome}{Revenue}
$$

### EBITDA margin

$$
EBITDAMargin=
\frac{EBITDA}{Revenue}
$$

---

# 33. Growth Calculations

### Revenue growth

$$
RevenueGrowth=
\frac{Revenue_t-Revenue_{t-1}}
{Revenue_{t-1}}
$$

### EPS growth

$$
EPSGrowth=
\frac{EPS_t-EPS_{t-1}}
{EPS_{t-1}}
$$

### CAGR

$$
CAGR=
\left(\frac{EndingValue}{BeginningValue}\right)^{1/n}-1
$$

Calculate CAGR for:

* revenue
* EPS
* FCF
* EBITDA
* dividends

---

# 34. Cash Flow Calculations

### Free cash flow

$$
FCF=OperatingCashFlow-CapEx
$$

### FCF margin

$$
FCFMargin=
\frac{FCF}{Revenue}
$$

### FCF yield

$$
FCFYield=
\frac{FCF}{MarketCap}
$$

### FCF growth

$$
FCFGrowth=
\frac{FCF_t-FCF_{t-1}}{FCF_{t-1}}
$$

---

# 35. Balance-Sheet Risk

### Debt/equity

$$
D/E=\frac{TotalDebt}{ShareholdersEquity}
$$

### Debt/EBITDA

$$
Debt/EBITDA=
\frac{TotalDebt}{EBITDA}
$$

### Net debt

$$
NetDebt=TotalDebt-Cash
$$

### Net debt/EBITDA

$$
NetDebt/EBITDA=
\frac{NetDebt}{EBITDA}
$$

### Current ratio

$$
CurrentRatio=
\frac{CurrentAssets}{CurrentLiabilities}
$$

### Quick ratio

$$
QuickRatio=
\frac{Cash+MarketableSecurities+Receivables}
{CurrentLiabilities}
$$

---

# 36. Return on Capital

### ROE

$$
ROE=
\frac{NetIncome}{AverageShareholdersEquity}
$$

### ROA

$$
ROA=
\frac{NetIncome}{AverageTotalAssets}
$$

### ROIC

$$
ROIC=
\frac{NOPAT}{InvestedCapital}
$$

These are particularly useful for **quality scoring**.

---

# 37. Earnings Surprise Calculations

### EPS surprise

$$
EPSSurprise\%=
\frac{ActualEPS-ExpectedEPS}
{|ExpectedEPS|}\times100
$$

### Revenue surprise

$$
RevenueSurprise\%=
\frac{ActualRevenue-ExpectedRevenue}
{ExpectedRevenue}\times100
$$

### Surprise consistency

$$
BeatRate=
\frac{\#Beats}{TotalQuarters}
$$

### Average surprise

$$
AvgSurprise=
\frac{1}{N}\sum Surprise_i
$$

---

# 38. Analyst Estimate Calculations

### Estimate revision

$$
Revision\%=
\frac{NewEstimate-OldEstimate}
{|OldEstimate|}\times100
$$

### Revision momentum

$$
RevisionMomentum=
EMA(NewEstimate-OldEstimate)
$$

Calculate for:

* EPS
* revenue
* EBITDA
* FCF

### Analyst dispersion

$$
Dispersion=
\frac{StdDev(Estimates)}
{Mean(Estimates)}
$$

High dispersion = greater uncertainty.

---

# 39. Valuation Relative to History

Instead of only looking at current P/E:

$$
PEZ=
\frac{PE_t-\mu_{PE}}
{\sigma_{PE}}
$$

Likewise:

* EV/EBITDA Z-score
* P/S Z-score
* P/FCF Z-score
* FCF yield percentile

This tells you whether a stock is **expensive/cheap relative to its own history**.

---

# 40. Peer Valuation

For peer group \(i=1...N\):

$$
RelativePE=
\frac{PE_{stock}}
{Median(PE_{peers})}
$$

Similarly:

$$
RelativeEVEBITDA=
\frac{EV/EBITDA_{stock}}
{Median(EV/EBITDA_{peers})}
$$

---

# 41. Composite Quant Scores

Once the raw calculations exist, normalize them.

### Min-max normalization

$$
Score=
100\times
\frac{x-Min(x)}
{Max(x)-Min(x)}
$$

### Z-score normalization

$$
Z=\frac{x-\mu}{\sigma}
$$

Then create factor scores.

### Momentum score

$$
M=w_1M_1+w_2M_2+...+w_nM_n
$$

### Quality score

$$
Q=w_1ROIC+w_2Margin+w_3FCFGrowth-w_4Leverage
$$

### Value score

$$
V=w_1PE+w_2EVEBITDA+w_3FCFYield+...
$$

Make sure signs are adjusted so that **higher score always means better**.

---

# 42. Risk Score

Example:

$$
RiskScore=
w_1Volatility+
w_2Beta+
w_3Drawdown+
w_4Leverage+
w_5LiquidityRisk
$$

You can further divide it into:

* market risk
* volatility risk
* liquidity risk
* fundamental risk
* valuation risk
* event risk

---

# 43. Regime Score

For a system such as yours, I would explicitly calculate:

$$
RegimeScore=
w_1Trend+
w_2Volatility+
w_3Momentum+
w_4MarketBreadth+
w_5RelativeStrength
$$

Then classify:

|     Score | Regime         |
| --------: | -------------- |
| Very high | Strong bullish |
|      High | Bullish        |
|   Neutral | Neutral        |
|       Low | Bearish        |
|  Very low | Strong bearish |

This becomes the input to your **strategy gates**.

---

# 44. Signal Quality / Confluence

Instead of relying on one indicator:

$$
ConfluenceScore=
\sum_{i=1}^{N}w_iSignal_i
$$

For example:

$$
Score=
20\%Trend+
20\%Momentum+
20\%Volatility+
15\%Volume+
15\%RelativeStrength+
10\%MarketRegime
$$

This is much more robust than:

> RSI < 30 → BUY

---

# 45. Probability / Historical Outcome Calculations

This is where your system becomes much more quantitative.

For a historical condition \(C\):

$$
P(Profit|C)=
\frac{\#WinningOccurrences}
{\#TotalOccurrences}
$$

### Expected return

$$
E[R|C]=
\sum_iP_iR_i
$$

### Win rate

$$
WinRate=
\frac{Wins}{Trades}
$$

### Average winner

$$
AvgWin=
\frac{\sum WinningReturns}{Wins}
$$

### Average loser

$$
AvgLoss=
\frac{\sum LosingReturns}{Losses}
$$

### Expectancy

$$
Expectancy=
WinRate\times AvgWin
-
LossRate\times |AvgLoss|
$$

This is one of the most important formulas for validating a research signal.

---

# 46. Maximum Favorable / Adverse Excursion

For every historical signal:

### MFE

$$
MFE=
\max\left(
\frac{FutureHigh-Entry}{Entry}
\right)
$$

### MAE

$$
MAE=
\min\left(
\frac{FutureLow-Entry}{Entry}
\right)
$$

This helps determine:

* stop-loss
* take-profit
* expected upside
* expected downside
* holding period

---

# 47. Forward Return Analysis

For a signal occurring at \(t\):

$$
FR_n=
\frac{P_{t+n}}{P_t}-1
$$

Calculate:

* 1D forward return
* 3D
* 5D
* 10D
* 20D
* 30D
* 60D

Then calculate:

$$
Mean(FR_n)
$$

$$
Median(FR_n)
$$

$$
WinRate(FR_n)
$$

$$
StdDev(FR_n)
$$

This is extremely useful for determining whether a research signal actually has predictive value.

---

# 48. Information Coefficient

For quantitative factor research:

$$
IC=Corr(Factor_t,ForwardReturn_{t+n})
$$

For example:

$$
IC=
Corr(RSI,ForwardReturn_{20})
$$

Calculate:

* mean IC
* median IC
* IC standard deviation
* IC consistency
* rolling IC

---

# 49. Factor Exposure

You can calculate whether a stock behaves like:

* momentum
* value
* quality
* size
* volatility
* growth

A simplified factor model:

$$
R_i=
\alpha+
\beta_M M+
\beta_V V+
\beta_Q Q+
\beta_S S+
\epsilon
$$

The coefficients measure exposure to each factor.

---

# 50. Research-Phase Event Risk

Quantify event proximity:

$$
DaysToEarnings=EarningsDate-CurrentDate
$$

Then create:

$$
EventRiskScore=f(DaysToEarnings,HistoricalMove)
$$

Historical earnings move:

$$
EarningsMove=
\frac{|Open_{post}-Close_{pre}|}
{Close_{pre}}
$$

Average earnings move:

$$
AvgEarningsMove=
\frac{1}{N}\sum EarningsMove_i
$$

---

# 51. Gap / Earnings Volatility

Calculate historical post-earnings volatility:

$$
EarningsVol=
StdDev(EarningsReturns)
$$

and:

$$
ExpectedMove\approx
Average(|EarningsMove|)
$$

This is useful for determining whether a strategy should **block or reduce exposure before earnings**.

---

# 52. Seasonality

For month \(m\):

$$
AvgReturn_m=
\frac{1}{N_m}\sum R_m
$$

### Positive-month probability

$$
P_m=
\frac{\#PositiveMonths}
{\#TotalMonths}
$$

### Seasonal strength

$$
SeasonalityScore=
\frac{AvgReturn_m}{StdDev(Return_m)}
$$

You can calculate seasonality by:

* month
* week of year
* day of week
* earnings cycle

---

# 53. Autocorrelation

$$
\rho_k=
Corr(R_t,R_{t-k})
$$

Useful for identifying:

* momentum persistence
* mean reversion
* serial dependence

---

# 54. Hurst Exponent

Useful for distinguishing trending vs mean-reverting behavior.

Conceptually:

$$
R/S\sim N^H
$$

where \(H\) is the Hurst exponent.

Rough interpretation:

* \(H>0.5\): persistence/trending
* \(H<0.5\): mean reversion
* \(H\approx0.5\): random-walk-like

---

# 55. Regime Change Detection

Calculate changes in:

$$
\Delta Volatility
$$

$$
\Delta Trend
$$

$$
\Delta Correlation
$$

$$
\Delta Breadth
$$

$$
\Delta Momentum
$$

and optionally use statistical change-point detection.

This is particularly important because a strategy can work beautifully in one regime and fail badly in another.

---

# 56. Composite "Research State"

For your system, I would ultimately consolidate all of the above into something like:

$$
ResearchState=
\{
Trend,
Momentum,
Volatility,
Volume,
Liquidity,
RelativeStrength,
MarketRegime,
Fundamentals,
Valuation,
Earnings,
Risk,
Seasonality
\}
$$

Then produce:

### Opportunity score

$$
OpportunityScore=
\sum w_iFactor_i
$$

### Risk score

$$
RiskScore=
\sum w_iRisk_i
$$

### Expected return

$$
ExpectedReturn=
E[R|CurrentConditions]
$$

### Risk/reward

$$
RR=
\frac{ExpectedUpside}
{ExpectedDownside}
$$

### Final research score

For example:

$$
FinalScore=
OpportunityScore
-\lambda RiskScore
$$

---

# Recommended Architecture for Your Quant System

Given the quant system you've been working on, I would **not** put all these calculations into one giant indicator engine.

I'd organize them like this:

```text
MARKET RESEARCH
│
├── 01 Price Structure
│   ├── Returns
│   ├── OHLC
│   ├── Gaps
│   └── Breakouts
│
├── 02 Trend
│   ├── SMA
│   ├── EMA
│   ├── MA slope
│   ├── MA alignment
│   └── ADX
│
├── 03 Momentum
│   ├── RSI
│   ├── ROC
│   ├── MACD
│   └── Stochastic
│
├── 04 Volatility
│   ├── ATR
│   ├── Standard deviation
│   ├── Bollinger Bands
│   ├── BB Width
│   └── Volatility regime
│
├── 05 Volume / Liquidity
│   ├── RVOL
│   ├── OBV
│   ├── VWAP
│   ├── Dollar volume
│   └── Turnover
│
├── 06 Relative Strength
│   ├── vs SPY
│   ├── vs QQQ
│   ├── vs Sector
│   └── vs Industry
│
├── 07 Market Regime
│   ├── SPY trend
│   ├── QQQ trend
│   ├── VIX
│   ├── Breadth
│   └── Correlation
│
├── 08 Fundamentals
│   ├── Growth
│   ├── Profitability
│   ├── Cash Flow
│   ├── Leverage
│   └── ROIC
│
├── 09 Valuation
│   ├── P/E
│   ├── PEG
│   ├── EV/EBITDA
│   ├── FCF Yield
│   └── Historical valuation
│
├── 10 Earnings / Estimates
│   ├── EPS surprise
│   ├── Revenue surprise
│   ├── Estimate revisions
│   └── Analyst dispersion
│
├── 11 Statistical Research
│   ├── Z-score
│   ├── Correlation
│   ├── Beta
│   ├── Alpha
│   ├── IC
│   ├── Autocorrelation
│   └── Hurst
│
└── 12 Quant Scoring
    ├── Trend Score
    ├── Momentum Score
    ├── Volatility Score
    ├── Quality Score
    ├── Value Score
    ├── Risk Score
    ├── Regime Score
    └── Final Opportunity Score
```

## The most important distinction

For your system, I would separate **calculation → interpretation → gate → signal**:

```text
RAW MARKET DATA
       ↓
INDICATOR CALCULATIONS
       ↓
STATISTICAL FEATURES
       ↓
REGIME CLASSIFICATION
       ↓
RESEARCH SCORES
       ↓
STRATEGY-SPECIFIC GATES
       ↓
ENTRY / EXIT SIGNAL
       ↓
EXECUTION
```

For example:

```text
Price
  ↓
SMA20 / SMA50 / SMA200
  ↓
Trend features
  ↓
Bull/Bear/Neutral regime
  ↓
Trend score
  ↓
MR gate / Momentum gate
  ↓
Signal
```

That separation is important because **RSI, Bollinger Bands, ATR, etc. are calculations—not trading decisions**. Your gates should consume those calculations and decide whether a particular strategy is allowed to operate.