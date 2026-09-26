Yes. For your architecture, I would define **MarketScore** as the quantitative score describing the **stock's current market behavior**—price trend, momentum, relative strength, volatility, volume, liquidity, market participation, mean reversion, and market-relative behavior.

That is slightly different from a pure **TechnicalScore**. In your system, I would make MarketScore the broad **observable market-state layer**, while TechnicalScore can remain more indicator/trading-pattern oriented. This separation is useful because institutional factor frameworks commonly distinguish Momentum, Volatility, Liquidity, Size, etc. as separate market characteristics. MSCI, for example, groups equity descriptors into Value, Size, Momentum, Volatility, Quality, Yield, Growth and Liquidity. ([MSCI][1])

Below is the exhaustive formula library I would consider.

---

# 1. Return calculations

## 1.1 Simple return

$$
R_t=\frac{P_t}{P_{t-n}}-1
$$

Typical horizons:

```text
1D
3D
5D
10D
20D
21D
63D
126D
252D
504D
756D
```

---

## 1.2 Log return

$$
r_t=\ln\left(\frac{P_t}{P_{t-1}}\right)
$$

Useful because multi-period log returns are additive:

$$
r_{t,n}=\sum_{i=0}^{n-1}r_{t-i}
$$

---

## 1.3 Total return

If dividends are included:

$$
TR_t=\frac{P_t+D_t}{P_{t-1}}-1
$$

For a total-return index:

$$
TR_t=\frac{Index_t}{Index_{t-1}}-1
$$

For equity scoring, use **adjusted prices** where appropriate so splits/dividends do not create artificial signals.

---

# 2. Multi-horizon momentum

Calculate:

$$
Momentum_n=\frac{P_t}{P_{t-n}}-1
$$

for:

$$
n\in\{5,10,21,63,126,252\}
$$

giving:

* 1-week momentum
* 2-week momentum
* 1-month momentum
* 3-month momentum
* 6-month momentum
* 12-month momentum

A multi-horizon momentum score:

$$
M=
w_1M_{21}
+w_2M_{63}
+w_3M_{126}
+w_4M_{252}
$$

This is consistent with institutional momentum methodologies; MSCI's momentum methodology combines 6-month and 12-month price performance and risk-adjusts the resulting momentum measure. ([MSCI][2])

---

# 3. Momentum excluding the most recent month

A very useful academic momentum calculation is:

$$
MOM_{12-1}=
\frac{P_{t-21}}{P_{t-252}}-1
$$

In other words, approximately the previous 12 months while skipping the most recent month.

This avoids mixing intermediate-term momentum with very-short-term reversal.

AQR describes a classic momentum construction using prior 12-month return while skipping the most recent month. ([AQR Images][3])

---

# 4. Momentum acceleration

Momentum level:

$$
M_t=R_{t,n}
$$

Momentum acceleration:

$$
MA_t=M_t-M_{t-1}
$$

Example:

$$
MomentumAcceleration=
3MReturn_t-3MReturn_{t-21}
$$

You can go further:

$$
MomentumJerk=
MA_t-MA_{t-1}
$$

This is useful for identifying:

> strong momentum → weakening momentum → reversal

---

# 5. Trend calculations

## 5.1 Price vs moving average

$$
PMA_n=\frac{P_t}{SMA_n}-1
$$

Examples:

$$
PMA_{20}
$$

$$
PMA_{50}
$$

$$
PMA_{100}
$$

$$
PMA_{200}
$$

---

## 5.2 Moving-average slope

$$
Slope_{MA,n}=
\frac{MA_{n,t}-MA_{n,t-k}}
{MA_{n,t-k}}
$$

For example:

$$
Slope_{SMA200}=
\frac{SMA200_t-SMA200_{t-20}}
{SMA200_{t-20}}
$$

---

## 5.3 Moving-average hierarchy

Binary signals:

$$
MAHierarchy=
I(P>MA20)+
I(MA20>MA50)+
I(MA50>MA100)+
I(MA100>MA200)
$$

Range:

$$
0\rightarrow4
$$

---

## 5.4 Golden/death-cross spread

$$
MACrossSpread=
\frac{MA50-MA200}{MA200}
$$

Positive:

$$
MA50>MA200
$$

Negative:

$$
MA50<MA200
$$

---

# 6. Distance from high/low

## 6.1 52-week high distance

$$
High52Gap=
\frac{P_t}{High_{252}}-1
$$

---

## 6.2 52-week low distance

$$
Low52Gap=
\frac{P_t}{Low_{252}}-1
$$

---

## 6.3 Percent of 52-week range

$$
RangePosition=
\frac{P_t-Low_{252}}
{High_{252}-Low_{252}}
$$

Range:

$$
0\leq RangePosition\leq1
$$

or 0–100.

---

## 6.4 Distance from all-time high

$$
ATHDrawdown=
\frac{P_t}{ATH}-1
$$

---

# 7. Drawdown

Current drawdown:

$$
DD_t=
\frac{P_t}{RollingHigh_t}-1
$$

Maximum drawdown:

$$
MDD=
\min_t DD_t
$$

For a rolling window:

$$
MDD_n=
\min_{t-n:t}
\left(
\frac{P_t}{RollingHigh_t}-1
\right)
$$

---

# 8. Drawdown recovery

Recovery from drawdown:

$$
Recovery=
\frac{P_t-Trough}{Peak-Trough}
$$

A useful measure is:

$$
RecoveryRate=
\frac{CurrentPrice-Trough}
{Peak-Trough}
$$

---

# 9. Time-under-water

Number of days since previous equity high:

$$
TUW=t-t_{lastATH}
$$

Or:

$$
TUW_{rolling}
=
\text{days below previous rolling high}
$$

This is a useful market-state variable.

---

# 10. Relative strength vs benchmark

Let benchmark return be \(R_B\).

$$
RS_n=R_{stock,n}-R_{benchmark,n}
$$

or:

$$
RSRatio_n=
\frac{1+R_{stock,n}}
{1+R_{benchmark,n}}-1
$$

Examples:

```text
Stock vs SPY
Stock vs QQQ
Stock vs sector ETF
Stock vs industry index
```

---

# 11. Relative strength ratio

$$
RSRatio_t=
\frac{P_{stock,t}}
{P_{benchmark,t}}
$$

Then:

$$
RSROC_n=
\frac{RSRatio_t}
{RSRatio_{t-n}}-1
$$

This tells you whether the stock is outperforming the benchmark.

---

# 12. Relative momentum percentile

For a universe of stocks:

$$
MomentumPercentile_i=
PercentileRank(R_i)
$$

For example:

$$
MomentumPercentile=
PercentileRank(6M\ Return)
$$

This is generally much more useful for stock selection than absolute return alone.

---

# 13. Sector-relative momentum

$$
SectorRelativeReturn=
R_{stock}-R_{sector}
$$

Then:

$$
SectorMomentumPercentile=
PercentileRank_{sector}(R_{stock})
$$

Industry-relative:

$$
IndustryRelativeReturn=
R_{stock}-R_{industry}
$$

Industry momentum is also used in institutional equity models; MSCI describes an industry-momentum factor based on relative strength within sub-industry groups. ([MSCI][4])

---

# 14. Risk-adjusted momentum

A particularly useful calculation:

$$
RAM_n=
\frac{R_n-R_f}
{\sigma_n}
$$

where:

$$
\sigma_n=AnnualizedVolatility_n
$$

This is essentially a Sharpe-like momentum measure.

MSCI explicitly uses excess return divided by annualized volatility in its risk-adjusted momentum methodology. ([MSCI][5])

---

# 15. Volatility

## 15.1 Historical volatility

Using log returns:

$$
\sigma_n=
Std(r_{t-n:t})
$$

Annualized:

$$
\sigma_{annual}
=
Std(r)\sqrt{252}
$$

---

# 16. Realized volatility

$$
RV_n=
\sqrt{
\sum_{i=1}^{n}r_i^2
}
$$

Annualized:

$$
RV_{annual}=
\sqrt{
252\sum r_i^2
}
$$

---

# 17. Downside volatility

$$
\sigma_{down}
=
Std(
\min(r_i,0)
)
$$

Annualized:

$$
\sigma_{down,annual}
=
\sigma_{down}\sqrt{252}
$$

---

# 18. Upside volatility

$$
\sigma_{up}
=
Std(
\max(r_i,0)
)
$$

---

# 19. Volatility ratio

$$
VolRatio=
\frac{\sigma_{short}}
{\sigma_{long}}
$$

For example:

$$
VolRatio=
\frac{\sigma_{20}}
{\sigma_{252}}
$$

Interpretation:

* > 1 = volatility expanding
* <1 = volatility contracting

---

# 20. Volatility acceleration

$$
VolAcceleration=
VolRatio_t-VolRatio_{t-1}
$$

---

# 21. ATR

True range:

$$
TR_t=
\max
\begin{cases}
H_t-L_t\\
|H_t-C_{t-1}|\\
|L_t-C_{t-1}|
\end{cases}
$$

Average true range:

$$
ATR_n=SMA(TR,n)
$$

Normalized:

$$
ATRPercent=
\frac{ATR_n}{P_t}
$$

---

# 22. ATR expansion

$$
ATRExpansion=
\frac{ATR_{short}}
{ATR_{long}}-1
$$

---

# 23. Beta

$$
\beta_i=
\frac{Cov(R_i,R_m)}
{Var(R_m)}
$$

Calculate:

```text
20D beta
60D beta
126D beta
252D beta
```

---

# 24. Rolling beta

$$
\beta_t=
\frac{Cov_t(R_i,R_m)}
{Var_t(R_m)}
$$

Then:

$$
\Delta\beta=
\beta_t-\beta_{t-n}
$$

This can identify changing market sensitivity.

---

# 25. Alpha

CAPM alpha:

$$
\alpha=
R_i-R_f-\beta(R_m-R_f)
$$

Rolling alpha:

$$
\alpha_n=
AnnualizedMean[
R_i-R_f-\beta(R_m-R_f)
]
$$

---

# 26. Information ratio

$$
IR=
\frac{R_i-R_B}
{TrackingError}
$$

where:

$$
TrackingError=
Std(R_i-R_B)
$$

Annualized:

$$
IR_{annual}=
\frac{Mean(R_i-R_B)}
{Std(R_i-R_B)}
\sqrt{252}
$$

---

# 27. Tracking error

$$
TE=
Std(R_i-R_B)\sqrt{252}
$$

---

# 28. Sharpe ratio

$$
Sharpe=
\frac{R_p-R_f}
{\sigma_p}
$$

Annualized:

$$
Sharpe_{annual}
=
\frac{Mean(r-r_f)}
{Std(r-r_f)}
\sqrt{252}
$$

---

# 29. Sortino ratio

$$
Sortino=
\frac{R_p-R_f}
{\sigma_{down}}
$$

---

# 30. Calmar ratio

$$
Calmar=
\frac{AnnualizedReturn}
{|MaximumDrawdown|}
$$

---

# 31. Gain/loss ratio

$$
GainLossRatio=
\frac{AveragePositiveReturn}
{|AverageNegativeReturn|}
$$

---

# 32. Hit rate

$$
HitRate=
\frac{\#(r_t>0)}
{N}
$$

---

# 33. Up/down capture

### Up capture

$$
UpCapture=
\frac{Mean(R_i|R_m>0)}
{Mean(R_m|R_m>0)}
$$

### Down capture

$$
DownCapture=
\frac{Mean(R_i|R_m<0)}
{Mean(R_m|R_m<0)}
$$

---

# 34. Volume calculations

## Average volume

$$
AvgVol_n=
\frac{1}{n}\sum_{i=1}^{n}Volume_i
$$

---

## Volume ratio

$$
VolumeRatio=
\frac{Volume_t}
{AvgVolume_n}
$$

---

## Relative volume

$$
RVOL=
\frac{Volume_t}
{AverageVolume_{n}}
$$

---

## Volume trend

$$
VolumeTrend=
\frac{AvgVolume_{20}}
{AvgVolume_{60}}-1
$$

---

# 35. Dollar volume

$$
DollarVolume_t=
Price_t\times Volume_t
$$

Average dollar volume:

$$
ADV_n=
SMA(DollarVolume,n)
$$

This is much more useful than share volume when comparing stocks with very different prices.

---

# 36. Liquidity

### Turnover

$$
Turnover=
\frac{Volume}
{SharesOutstanding}
$$

### Average turnover

$$
AvgTurnover_n=
SMA(Turnover,n)
$$

### Amihud illiquidity

$$
ILLIQ=
\frac{1}{N}
\sum_{t=1}^{N}
\frac{|R_t|}
{DollarVolume_t}
$$

Higher means less liquid.

### Amihud liquidity score

$$
LiquidityScore=-ILLIQ
$$

---

# 37. Price-volume relationship

### Price-volume correlation

$$
PVCorr=
Corr(R_t,Volume_t)
$$

### Return-dollar-volume correlation

$$
Corr(|R_t|,DollarVolume_t)
$$

---

# 38. Volume confirmation

A simple measure:

$$
VolumeConfirmation=
Sign(R_t)\times
\frac{Volume_t}
{AvgVolume_n}
$$

Positive price movement + high volume:

$$
Positive
$$

Negative price movement + high volume:

$$
Negative
$$

---

# 39. On-Balance Volume

$$
OBV_t=
OBV_{t-1}+
\begin{cases}
V_t & P_t>P_{t-1}\\
-V_t & P_t<P_{t-1}\\
0 & P_t=P_{t-1}
\end{cases}
$$

Then calculate:

$$
OBVSlope=
Slope(OBV,n)
$$

---

# 40. OBV divergence

Price momentum:

$$
M_P
$$

OBV momentum:

$$
M_{OBV}
$$

Then:

$$
OBVDivergence=
M_{OBV}-M_P
$$

Positive = volume is confirming price more strongly.

---

# 41. Accumulation/distribution

Money flow multiplier:

$$
MFM=
\frac{(Close-Low)-(High-Close)}
{High-Low}
$$

Money flow volume:

$$
MFV=MFM\times Volume
$$

A/D line:

$$
AD_t=AD_{t-1}+MFV_t
$$

---

# 42. Chaikin Money Flow

$$
CMF_n=
\frac{\sum_{i=1}^{n}MFV_i}
{\sum_{i=1}^{n}Volume_i}
$$

---

# 43. Money Flow Index

Typical calculation:

$$
TypicalPrice=
\frac{H+L+C}{3}
$$

$$
RawMoneyFlow=
TypicalPrice\times Volume
$$

Then:

$$
MFRatio=
\frac{PositiveMoneyFlow}
{NegativeMoneyFlow}
$$

$$
MFI=
100-\frac{100}{1+MFRatio}
$$

---

# 44. VWAP

$$
VWAP=
\frac{\sum Price_iVolume_i}
{\sum Volume_i}
$$

Distance:

$$
VWAPGap=
\frac{P_t}{VWAP}-1
$$

---

# 45. VWAP slope

$$
VWAPSlope=
\frac{VWAP_t-VWAP_{t-n}}
{VWAP_{t-n}}
$$

---

# 46. Price efficiency

A useful trend-quality measure:

$$
EfficiencyRatio=
\frac{|P_t-P_{t-n}|}
{\sum_{i=1}^{n}|P_i-P_{i-1}|}
$$

Range:

$$
0\leq ER\leq1
$$

Near 1:

> directional trend

Near 0:

> noisy movement

This is extremely useful for distinguishing **real trend** from random volatility.

---

# 47. Trend persistence

Define daily direction:

$$
D_t=
\begin{cases}
1&R_t>0\\
0&R_t\le0
\end{cases}
$$

Then:

$$
Persistence=
\frac{\sum D_t}{N}
$$

You can separately measure:

$$
UpDayRatio
$$

and:

$$
DownDayRatio
$$

---

# 48. Consecutive return streak

$$
Streak_t=
\begin{cases}
Streak_{t-1}+1&r_t>0\\
Streak_{t-1}-1&r_t<0
\end{cases}
$$

Useful for short-term exhaustion.

---

# 49. Mean reversion

## Distance from mean

$$
MeanDeviation=
\frac{P_t-SMA_n}{SMA_n}
$$

---

## Z-score

$$
ZPrice=
\frac{P_t-SMA_n}
{Std(P,n)}
$$

---

# 50. Return z-score

$$
ZReturn=
\frac{R_t-\mu_R}
{\sigma_R}
$$

---

# 51. Bollinger position

$$
UpperBand=SMA_n+k\sigma_n
$$

$$
LowerBand=SMA_n-k\sigma_n
$$

Then:

$$
BBPosition=
\frac{P-LowerBand}
{UpperBand-LowerBand}
$$

---

# 52. Bollinger bandwidth

$$
BBWidth=
\frac{UpperBand-LowerBand}
{MiddleBand}
$$

---

# 53. Bollinger bandwidth percentile

$$
BBPercentile=
PercentileRank(BBWidth)
$$

Useful for identifying volatility compression/expansion.

---

# 54. RSI

$$
RS=
\frac{AverageGain_n}
{AverageLoss_n}
$$

$$
RSI=
100-\frac{100}{1+RS}
$$

Calculate:

```text
RSI(2)
RSI(5)
RSI(14)
RSI(21)
RSI(50)
```

---

# 55. RSI momentum

$$
RSIMomentum=
RSI_t-RSI_{t-n}
$$

---

# 56. RSI divergence

Price:

$$
\Delta P
$$

RSI:

$$
\Delta RSI
$$

Bullish divergence:

$$
\Delta P<0
\quad\text{and}\quad
\Delta RSI>0
$$

Bearish divergence:

$$
\Delta P>0
\quad\text{and}\quad
\Delta RSI<0
$$

---

# 57. MACD

$$
MACD=
EMA_{12}-EMA_{26}
$$

Signal:

$$
Signal=EMA_9(MACD)
$$

Histogram:

$$
Histogram=MACD-Signal
$$

---

# 58. MACD momentum

$$
MACDAcceleration=
Histogram_t-Histogram_{t-n}
$$

---

# 59. Stochastic oscillator

$$
\%K=
100
\frac{C-L_n}
{H_n-L_n}
$$

$$
\%D=SMA(\%K,3)
$$

---

# 60. Rate of change

$$
ROC_n=
\frac{P_t-P_{t-n}}
{P_{t-n}}
\times100
$$

---

# 61. Average Directional Index

True range:

$$
TR
$$

Directional movements:

$$
+DM,\quad -DM
$$

Then:

$$
+DI=
100\frac{Smoothed(+DM)}
{ATR}
$$

$$
-DI=
100\frac{Smoothed(-DM)}
{ATR}
$$

$$
DX=
100
\frac{|+DI--DI|}
{+DI+-DI}
$$

$$
ADX=SMA(DX,n)
$$

ADX measures **trend strength**, not direction.

---

# 62. Directional bias

$$
DirectionalBias=
\frac{+DI--DI}
{+DI+-DI}
$$

Range:

$$
[-1,+1]
$$

---

# 63. Ichimoku calculations

Tenkan:

$$
Tenkan=
\frac{HighestHigh_9+LowestLow_9}{2}
$$

Kijun:

$$
Kijun=
\frac{HighestHigh_{26}+LowestLow_{26}}{2}
$$

Senkou A:

$$
SenkouA=
\frac{Tenkan+Kijun}{2}
$$

Senkou B:

$$
SenkouB=
\frac{HighestHigh_{52}+LowestLow_{52}}{2}
$$

Then:

$$
CloudThickness=
|SenkouA-SenkouB|
$$

---

# 64. Breakout calculations

### N-day breakout

$$
Breakout=
\frac{P_t}{HighestHigh_{n,t-1}}-1
$$

### Breakdown

$$
Breakdown=
\frac{P_t}{LowestLow_{n,t-1}}-1
$$

---

# 65. Breakout strength

$$
BreakoutStrength=
\frac{P_t-Resistance}
{ATR}
$$

---

# 66. Breakout volume confirmation

$$
BreakoutVolume=
\frac{Volume_t}
{AvgVolume_{20}}
$$

Combine:

$$
ConfirmedBreakout=
BreakoutStrength\times BreakoutVolume
$$

---

# 67. Gap calculations

### Overnight gap

$$
Gap_t=
\frac{Open_t-Close_{t-1}}
{Close_{t-1}}
$$

### Gap continuation

$$
GapContinuation=
Sign(Gap_t)\times Sign(Close_t-Open_t)
$$

---

# 68. Gap fill

For an upward gap:

$$
GapFill=
\frac{PriorClose-Low_t}
{Open_t-PriorClose}
$$

---

# 69. Intraday strength

$$
IntradayStrength=
\frac{Close-Low}
{High-Low}
$$

Range:

$$
0\rightarrow1
$$

Near 1 means the stock closed near the high.

---

# 70. Close location value

$$
CLV=
\frac{(Close-Low)-(High-Close)}
{High-Low}
$$

Range:

$$
[-1,1]
$$

---

# 71. Candle body strength

$$
BodyStrength=
\frac{|Close-Open|}
{High-Low}
$$

---

# 72. Upper/lower wick ratios

$$
UpperWick=
\frac{High-\max(Open,Close)}
{High-Low}
$$

$$
LowerWick=
\frac{\min(Open,Close)-Low}
{High-Low}
$$

---

# 73. Range expansion

$$
Range_t=High_t-Low_t
$$

$$
RangeExpansion=
\frac{Range_t}
{AverageRange_n}
$$

---

# 74. Volatility-adjusted return

$$
VAR=
\frac{R_n}{ATR\%}
$$

or:

$$
VAR=
\frac{R_n}{\sigma_n}
$$

---

# 75. Sharpe-like momentum

$$
MomentumSharpe_n=
\frac{Mean(r)}
{Std(r)}
\sqrt{252}
$$

---

# 76. Downside-adjusted momentum

$$
MomentumSortino=
\frac{Mean(r)}
{DownsideDeviation}
$$

---

# 77. Maximum adverse excursion

For a holding window:

$$
MAE=
\min_t
\left(
\frac{P_t-P_{entry}}
{P_{entry}}
\right)
$$

---

# 78. Maximum favorable excursion

$$
MFE=
\max_t
\left(
\frac{P_t-P_{entry}}
{P_{entry}}
\right)
$$

These are particularly useful if your MarketScore eventually becomes connected to trade execution.

---

# 79. Tail risk

## Downside quantile

$$
VaR_{\alpha}=Quantile(R,\alpha)
$$

For example:

$$
VaR_{5\%}=Quantile(R,0.05)
$$

---

## Expected Shortfall

$$
ES_{\alpha}
=
E[R|R\le VaR_{\alpha}]
$$

---

# 80. Skewness

$$
Skew=
\frac{E[(R-\mu)^3]}
{\sigma^3}
$$

---

# 81. Kurtosis

$$
Kurt=
\frac{E[(R-\mu)^4]}
{\sigma^4}
$$

Excess kurtosis:

$$
Kurtosis_{excess}=Kurtosis-3
$$

---

# 82. Return distribution stability

Calculate rolling:

$$
Skew_{20},Skew_{60},Skew_{252}
$$

$$
Kurt_{20},Kurt_{60},Kurt_{252}
$$

and their changes.

---

# 83. Autocorrelation

$$
ACF_k=
Corr(r_t,r_{t-k})
$$

Important:

* positive short-term autocorrelation → trend persistence
* negative short-term autocorrelation → reversal tendency

---

# 84. Partial autocorrelation

$$
PACF_k
$$

Useful for determining whether return persistence remains after controlling for intermediate lags.

---

# 85. Hurst exponent

Estimate:

$$
H
$$

Interpretation:

$$
H>0.5
$$

can indicate persistence/trending behavior.

$$
H<0.5
$$

can indicate anti-persistence/reversion.

$$
H\approx0.5
$$

is closer to random-walk behavior.

Use cautiously; estimator choice matters considerably.

---

# 86. Variance ratio

For \(k\)-period returns:

$$
VR(k)=
\frac{Var(r_t^{(k)})}
{kVar(r_t)}
$$

Interpretation:

$$
VR>1
$$

persistence.

$$
VR<1
$$

mean-reversion tendency.

---

# 87. Trend-to-noise ratio

$$
TNR=
\frac{|P_t-P_{t-n}|}
{\sum |P_i-P_{i-1}|}
$$

This is essentially closely related to the efficiency ratio.

---

# 88. Fractal dimension

A fractal-dimension estimate can be used to distinguish:

```text
trending
random
mean-reverting
```

A simplified relationship often used is:

$$
D\approx2-H
$$

where \(H\) is the Hurst exponent.

---

# 89. Market beta regimes

Calculate:

$$
\beta_{20}
$$

$$
\beta_{60}
$$

$$
\beta_{252}
$$

Then:

$$
BetaCompression=
\beta_{20}-\beta_{252}
$$

---

# 90. Idiosyncratic volatility

From:

$$
R_i=\alpha+\beta R_m+\epsilon
$$

calculate:

$$
IdioVol=Std(\epsilon)
$$

This separates stock-specific volatility from market-driven volatility.

MSCI's low-volatility framework, for example, explicitly considers beta and residual volatility rather than treating volatility as only one raw measure. ([MSCI][6])

---

# 91. Residual momentum

First remove market and sector exposure:

$$
R_i=
\alpha+\beta_mR_m+\beta_sR_s+\epsilon
$$

Then:

$$
ResidualMomentum=
\sum_{t=1}^{n}\epsilon_t
$$

This is a much cleaner measure of stock-specific momentum.

---

# 92. Market correlation

$$
\rho_{stock,market}
=
Corr(R_i,R_m)
$$

Also calculate:

$$
\rho_{stock,sector}
$$

$$
\rho_{stock,industry}
$$

---

# 93. Correlation regime

$$
CorrelationChange=
\rho_{short}-\rho_{long}
$$

This can identify:

> stock becoming increasingly market-driven.

---

# 94. Market breadth

For a universe:

$$
Advance_t=
\#Stocks(R_t>0)
$$

$$
Decline_t=
\#Stocks(R_t<0)
$$

---

# 95. Advance/decline ratio

$$
ADRatio=
\frac{Advances}
{Declines}
$$

---

# 96. Advance/decline line

$$
ADLine_t=
ADLine_{t-1}
+
Advances_t-Declines_t
$$

---

# 97. Breadth percentage

$$
Breadth=
\frac{Advances-Declines}
{Advances+Declines}
$$

Range:

$$
[-1,+1]
$$

---

# 98. Percent above moving average

For universe \(N\):

$$
PctAboveMA_n=
\frac{\#(P_i>MA_{n,i})}
{N}
$$

Examples:

$$
PctAbove50
$$

$$
PctAbove200
$$

---

# 99. New-high/new-low breadth

$$
NHNL=
NewHighs-NewLows
$$

Normalized:

$$
NHNLRatio=
\frac{NewHighs-NewLows}
{NewHighs+NewLows}
$$

---

# 100. Volume breadth

$$
UpVolume=
\sum Volume_i(R_i>0)
$$

$$
DownVolume=
\sum Volume_i(R_i<0)
$$

Then:

$$
VolumeBreadth=
\frac{UpVolume-DownVolume}
{UpVolume+DownVolume}
$$

---

# 101. Breadth thrust

$$
BreadthThrust=
\frac{AdvancingIssues}
{AdvancingIssues+DecliningIssues}
$$

Track the change over a short window.

---

# 102. Sector breadth

For sector \(s\):

$$
SectorBreadth_s=
\frac{Advancing_s-Declining_s}
{Advancing_s+Declining_s}
$$

This can be particularly useful for detecting **market regime changes**.

---

# 103. Sector-relative performance

$$
SectorAlpha=
R_{stock}-R_{sector}
$$

And:

$$
SectorRank=
PercentileRank(R_{stock}|Sector)
$$

---

# 104. Industry-relative performance

$$
IndustryAlpha=
R_{stock}-R_{industry}
$$

---

# 105. Market regime return

For benchmark:

$$
R_{m,20}
$$

$$
R_{m,60}
$$

$$
R_{m,252}
$$

Then classify:

```text
short-term
intermediate-term
long-term
```

without relying solely on a single indicator.

---

# 106. Market trend regime

Example continuous score:

$$
MarketTrend=
w_1Z(R_{20})+
w_2Z(R_{60})+
w_3Z(R_{252})+
w_4Z(P/MA200-1)
$$

---

# 107. Volatility regime

$$
VolRegime=
\frac{\sigma_{20}}
{\sigma_{252}}
$$

---

# 108. Volatility term structure

If implied volatility is available:

$$
IVTermStructure=
\frac{IV_{short}}
{IV_{long}}-1
$$

For example:

$$
\frac{VIX_{1M}}{VIX_{3M}}-1
$$

---

# 109. Realized vs implied volatility

$$
VolRiskPremium=
IV-RV
$$

or:

$$
VRP=
\frac{IV}{RV}-1
$$

This is particularly useful if options data is available.

---

# 110. Implied volatility percentile

$$
IVRank=
\frac{IV_t-Low(IV,n)}
{High(IV,n)-Low(IV,n)}
$$

---

# 111. IV percentile

$$
IVPercentile=
\frac{\#(IV_i<IV_t)}
{N}
$$

---

# 112. Put/call ratios

If options data exists:

$$
PCR=
\frac{PutVolume}
{CallVolume}
$$

Open-interest version:

$$
PCROI=
\frac{PutOpenInterest}
{CallOpenInterest}
$$

---

# 113. Short interest

$$
ShortInterestRatio=
\frac{SharesShort}
{Float}
$$

---

# 114. Days to cover

$$
DaysToCover=
\frac{SharesShort}
{AverageDailyVolume}
$$

---

# 115. Short-interest change

$$
\Delta SI=
\frac{SI_t}{SI_{t-n}}-1
$$

---

# 116. Short squeeze pressure

A composite could combine:

$$
SqueezePressure=
f(
ShortInterest,
DaysToCover,
Volume,
PriceMomentum,
Float
)
$$

Keep this separate from ordinary momentum because high short interest can mean either bearish positioning or potential forced buying.

---

# 117. Institutional ownership change

If data is available:

$$
InstitutionalFlow=
InstitutionalOwnership_t-
InstitutionalOwnership_{t-n}
$$

---

# 118. Insider transaction pressure

For aggregate insider activity:

$$
InsiderNet=
InsiderBuys-InsiderSells
$$

Value-weighted:

$$
InsiderNetValue=
BuyValue-SellValue
$$

This arguably belongs in your **Event/Sentiment** engine rather than MarketScore, so I wouldn't double-count it.

---

# 119. Market microstructure

If intraday/order-book data is available:

### Bid-ask spread

$$
Spread=
\frac{Ask-Bid}
{Mid}
$$

where:

$$
Mid=\frac{Ask+Bid}{2}
$$

---

# 120. Effective spread

$$
EffectiveSpread=
2|TradePrice-Mid|
$$

Normalized:

$$
EffectiveSpreadPct=
\frac{2|TradePrice-Mid|}
{Mid}
$$

---

# 121. Order imbalance

$$
OI=
\frac{BuyVolume-SellVolume}
{BuyVolume+SellVolume}
$$

---

# 122. Quote imbalance

$$
QI=
\frac{BidSize-AskSize}
{BidSize+AskSize}
$$

---

# 123. VPIN-style order-flow toxicity

A simplified volume imbalance:

$$
VI=
\frac{|BuyVolume-SellVolume|}
{TotalVolume}
$$

For intraday market-state analysis, this can become a useful liquidity-stress signal.

---

# 124. Market impact

A simplified price-impact estimate:

$$
Impact=
\frac{|\Delta P|}
{DollarVolume}
$$

Or estimate empirically:

$$
|\Delta P|
=
\alpha+
\lambda
\frac{OrderSize}
{ADV}
+\epsilon
$$

where \(\lambda\) is market impact sensitivity.

---

# 125. Liquidity-adjusted momentum

$$
LAM=
\frac{Momentum}
{ILLIQ}
$$

Or more safely:

$$
LAM=
Momentum\times LiquidityScore
$$

---

# 126. Volatility-adjusted relative strength

$$
VRS=
\frac{R_{stock}-R_{benchmark}}
{\sigma_{stock}}
$$

---

# 127. Relative Sharpe

$$
RelativeSharpe=
\frac{R_{stock}-R_{benchmark}}
{TrackingError}
$$

---

# 128. Momentum consistency

Calculate returns over several periods:

$$
M_{5},M_{21},M_{63},M_{126},M_{252}
$$

Then:

$$
MomentumConsistency=
\frac{\#(M_n>0)}
{N}
$$

---

# 129. Multi-horizon trend agreement

$$
TrendAgreement=
\frac{
I(P>MA20)+
I(P>MA50)+
I(P>MA100)+
I(P>MA200)
}{4}
$$

---

# 130. Multi-factor market score

Now we get to the part most relevant to your system.

Instead of putting all 100+ calculations directly into one formula, organize them into factor families.

A good architecture is:

```text
MARKET SCORE
│
├── Momentum
│   ├── Absolute momentum
│   ├── Relative momentum
│   ├── Sector momentum
│   ├── Momentum acceleration
│   └── Momentum consistency
│
├── Trend
│   ├── MA positioning
│   ├── MA slope
│   ├── Trend hierarchy
│   ├── Breakouts
│   └── Trend efficiency
│
├── Volatility
│   ├── Realized volatility
│   ├── ATR
│   ├── Downside volatility
│   ├── Volatility expansion
│   └── Tail risk
│
├── Volume / Flow
│   ├── Relative volume
│   ├── OBV
│   ├── CMF
│   ├── A/D
│   └── Volume confirmation
│
├── Relative Strength
│   ├── Market
│   ├── Sector
│   ├── Industry
│   └── Cross-sectional rank
│
├── Mean Reversion
│   ├── Distance from MA
│   ├── Z-score
│   ├── RSI
│   ├── Bollinger position
│   └── Short-term reversal
│
├── Liquidity
│   ├── ADV
│   ├── Turnover
│   ├── Amihud
│   └── Spread
│
├── Market Regime
│   ├── Benchmark trend
│   ├── Market breadth
│   ├── Volatility regime
│   ├── Correlation regime
│   └── Risk-on/risk-off
│
└── Risk-Adjusted Performance
    ├── Sharpe
    ├── Sortino
    ├── Information ratio
    ├── Calmar
    └── Beta-adjusted return
```

---

# 131. Factor normalization

This is critical.

Do **not** simply add raw RSI, returns, volatility, beta, etc.

For each factor:

$$
Z_i=
\frac{X_i-\mu_X}{\sigma_X}
$$

Prefer sector-relative or universe-relative normalization where appropriate.

MSCI's methodologies explicitly use cross-sectional standardization and winsorization for factor scores. ([MSCI][6])

---

# 132. Robust normalization

For outlier-heavy market variables:

$$
RobustZ_i=
\frac{X_i-Median(X)}
{1.4826\times MAD}
$$

Then winsorize:

$$
Z'_i=
\max(-3,\min(3,Z_i))
$$

---

# 133. Percentile transformation

Another excellent option:

$$
P_i=PercentileRank(X_i)
$$

Then:

$$
Score_i=100P_i
$$

This makes the score very easy to interpret.

---

# 134. Direction normalization

For a higher-is-better factor:

$$
S_i=PercentileRank(X_i)
$$

For a lower-is-better factor:

$$
S_i=1-PercentileRank(X_i)
$$

For example:

```text
Momentum          higher = better
Relative strength higher = better
Sharpe            higher = better
Volatility        lower = better
Drawdown          lower = better
Amihud            lower = better
Beta              context dependent
```

---

# 135. Market factor subscores

I would produce:

$$
MomentumScore
$$

$$
TrendScore
$$

$$
RelativeStrengthScore
$$

$$
VolumeScore
$$

$$
VolatilityScore
$$

$$
LiquidityScore
$$

$$
MeanReversionScore
$$

$$
MarketRegimeScore
$$

$$
RiskAdjustedScore
$$

all normalized to:

$$
0-100
$$

---

# 136. Composite MarketScore

For example:

$$
MarketScore=
w_M Momentum+
w_T Trend+
w_R RelativeStrength+
w_V Volume+
w_\sigma Volatility+
w_L Liquidity+
w_{MR} MeanReversion+
w_{Regime} MarketRegime+
w_{RA} RiskAdjusted
$$

The weights should ultimately be learned/backtested rather than assumed.

---

# 137. A practical initial weighting

For **your system**, I would initially test something around:

| Market factor             | Initial research weight |
| ------------------------- | ----------------------: |
| Momentum                  |                     20% |
| Trend                     |                     15% |
| Relative Strength         |                     15% |
| Volume/Flow               |                     10% |
| Volatility                |                     10% |
| Liquidity                 |                      5% |
| Mean Reversion            |                     10% |
| Market Regime             |                     10% |
| Risk-Adjusted Performance |                      5% |
| **Total**                 |                **100%** |

These are **starting research parameters, not a claim that these weights are optimal**.

Institutional methodologies commonly use multiple descriptors within a factor rather than depending on one indicator, which supports this hierarchical approach. ([MSCI][7])

---

# 138. The important part for your system: don't double-count

This is where I'd be particularly careful with your existing **TechnicalScore + MarketScore** architecture.

For example:

```text
RSI
MACD
ADX
Bollinger
ATR
SMA50
SMA200
```

are all highly related.

If you give each one a separate 10% weight, you have accidentally created:

> Trend/momentum = 70%

even though your formula appears diversified.

Instead:

$$
TechnicalSubscore=
f(RSI,MACD,ADX,Bollinger,ATR)
$$

and:

$$
MarketMomentum=
f(1M,3M,6M,12M,relative\ momentum)
$$

Then control the top-level weights.

---

# 139. Recommended separation in your architecture

Given your existing engines, I would define the boundary approximately like this:

### FundamentalScore

```text
Financial statements
Profitability
Growth
Cash flow
Balance sheet
Capital allocation
Valuation
Earnings quality
```

### MarketScore

```text
Price behavior
Returns
Relative strength
Momentum
Volume
Liquidity
Volatility
Market regime
Breadth
Cross-sectional ranking
```

### TechnicalScore

```text
RSI
MACD
ADX
Bollinger
Stochastic
Ichimoku
Support/resistance
Breakout patterns
Candle structure
Short-term mean reversion
```

### RegimeScore

```text
Market trend
VIX/volatility regime
Breadth regime
Correlation regime
Yield curve
Rates
Credit
Macro risk
Risk-on/risk-off
```

This prevents the same information from voting multiple times.

---

# 140. The MarketScore I'd actually build for your application

I would make the deterministic engine output something like:

```text
MarketScore: 76.4

MomentumScore:             84.2
TrendScore:                79.6
RelativeStrengthScore:     88.1
VolumeFlowScore:           72.3
VolatilityScore:           61.5
LiquidityScore:            93.2
MeanReversionScore:        48.7
MarketRegimeScore:         70.4
RiskAdjustedScore:         75.8

MarketCoverage:            96%
MarketDataFreshness:       99%
MarketFactorAgreement:     81%
MarketConfidence:          87%

Key positives:
  + 6M relative strength
  + 3M momentum
  + price > 50/100/200 DMA
  + strong volume confirmation

Key negatives:
  - elevated short-term volatility
  - RSI near upper tail
  - declining momentum acceleration
```

Then:

$$
\boxed{
MarketScore=
\sum_{k=1}^{9}
w_kMarketFactor_k
}
$$

while **MarketConfidence remains separate**.

That last distinction is especially important for the architecture you've been developing: a stock can have a **high MarketScore but low confidence** if, for example, only 40% of the market-data factors are available or the factors strongly disagree. You don't want missing data to silently turn into a neutral 50 and then contaminate the composite.

The broad factor structure also has a strong precedent: MSCI's factor framework explicitly treats Momentum, Volatility and Liquidity as distinct style dimensions, while its momentum methodology uses multiple horizons and risk adjustment rather than one raw return number. ([MSCI][1])

**One important design recommendation for your system:** I would not implement all ~130 calculations as independent votes. I'd implement them as **raw indicators → correlated-indicator clusters → factor subscores → MarketScore**. That gives you a very large calculation library without allowing 15 different versions of “price is trending upward” to overwhelm the rest of the scorecard.

[1]: https://www.msci.com/research-and-insights/blog-post/creating-a-common-language-for-factor-investing?utm_source=chatgpt.com "Creating a common language for factor investing | MSCI"
[2]: https://www.msci.com/documents/10199/242721/MSCI_Factor_Indices.pdf/74fe7772-583f-402a-8d91-49a2525d9f0c?utm_source=chatgpt.com "MSCI Factor Indexes"
[3]: https://images.aqr.com/-/media/AQR/Documents/Whitepapers/More-Superstar-InvestorsSpains-Value-Investors.pdf?utm_source=chatgpt.com "Appendix

Factor Descriptions

\**Market:** MSCI Eu"
[4]: https://www.msci.com/research-and-insights/blog-post/understanding-the-industry-momentum-factor?utm_source=chatgpt.com "Understanding the Industry-Momentum Factor | MSCI"
[5]: https://www.msci.com/documents/10199/43a8f9da-ba1e-4802-905a-90db7ea999f8?utm_source=chatgpt.com "METHODOLOGY HIGHLIGHTS"
[6]: https://www.msci.com/indexes/documents/methodology/3_MSCI_Factor_Advanced_Indexes_Methodology_20250203.pdf?utm_source=chatgpt.com "MSCI Factor Advanced Series Indexes Methodology"
[7]: https://www.msci.com/research-and-insights/blog-post/how-to-describe-a-factor?utm_source=chatgpt.com "How to Describe a Factor | MSCI"
