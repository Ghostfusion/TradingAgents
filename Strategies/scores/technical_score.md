Absolutely. For your architecture, I would make **TechnicalScore** the quantitative assessment of the stock's **technical condition and setup quality**, while keeping the broader **MarketScore** focused on market behavior/factor exposure such as momentum, relative strength, liquidity, volatility, and cross-sectional market characteristics.

That distinction prevents RSI, MACD, moving averages, momentum, etc. from being counted multiple times across engines.

Below is a comprehensive technical-indicator/formula library.

---

# 1. Price-derived calculations

Let:

* \(O_t\) = open
* \(H_t\) = high
* \(L_t\) = low
* \(C_t\) = close
* \(V_t\) = volume

## Simple return

$$
R_t=\frac{C_t}{C_{t-1}}-1
$$

## Log return

$$
r_t=\ln\left(\frac{C_t}{C_{t-1}}\right)
$$

## N-period return

$$
R_n=\frac{C_t}{C_{t-n}}-1
$$

## N-period ROC

$$
ROC_n=
100\left(\frac{C_t-C_{t-n}}{C_{t-n}}\right)
$$

---

# 2. Moving averages

## SMA

$$
SMA_n=
\frac{1}{n}\sum_{i=0}^{n-1}C_{t-i}
$$

Typical:

```text
SMA5
SMA10
SMA20
SMA50
SMA100
SMA150
SMA200
```

## EMA

$$
EMA_t=
\alpha C_t+(1-\alpha)EMA_{t-1}
$$

where

$$
\alpha=\frac{2}{n+1}
$$

## WMA

$$
WMA=
\frac{\sum_{i=1}^{n}iC_i}
{\sum_{i=1}^{n}i}
$$

## HMA

$$
HMA_n=
WMA_{\sqrt n}
\left(
2WMA_{n/2}-WMA_n
\right)
$$

---

# 3. Moving-average positioning

## Price vs SMA

$$
MADeviation_n=
\frac{C_t-SMA_n}{SMA_n}
$$

Examples:

$$
C/SMA20-1
$$

$$
C/SMA50-1
$$

$$
C/SMA200-1
$$

## Price above/below MA

$$
MAState_n=
I(C_t>SMA_n)
$$

## Multi-MA alignment

$$
MAAlignment=
I(C>SMA20)+
I(C>SMA50)+
I(C>SMA100)+
I(C>SMA200)
$$

---

# 4. Moving-average slopes

$$
MASlope_n=
\frac{MA_{n,t}-MA_{n,t-k}}
{MA_{n,t-k}}
$$

Examples:

$$
Slope_{MA20}
$$

$$
Slope_{MA50}
$$

$$
Slope_{MA200}
$$

Normalize by ATR if desired:

$$
MASlopeATR=
\frac{MA_t-MA_{t-k}}
{ATR_n}
$$

---

# 5. Moving-average crossovers

## Golden cross

$$
I(MA50>MA200)
$$

## Death cross

$$
I(MA50<MA200)
$$

## Crossover spread

$$
CrossSpread=
\frac{MA50-MA200}{MA200}
$$

## Crossover velocity

$$
CrossVelocity=
CrossSpread_t-CrossSpread_{t-k}
$$

This is better than a binary golden/death-cross flag because it measures **how rapidly the relationship is changing**.

---

# 6. EMA crossover systems

For example:

$$
EMA_{12}-EMA_{26}
$$

and:

$$
EMA_{5}-EMA_{20}
$$

Normalize:

$$
EMAStack=
\frac{EMA_{fast}-EMA_{slow}}
{ATR}
$$

---

# 7. MACD

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

## MACD slope

$$
MACDSlope=
MACD_t-MACD_{t-k}
$$

## Histogram slope

$$
HistogramSlope=
Histogram_t-Histogram_{t-k}
$$

## Histogram acceleration

$$
HistogramAcceleration=
\Delta Histogram_t-\Delta Histogram_{t-1}
$$

---

# 8. MACD crossover

$$
MACDCross=
I(MACD>Signal)
$$

Normalized distance:

$$
MACDSpread=
\frac{MACD-Signal}{ATR}
$$

---

# 9. RSI

$$
RS=
\frac{AverageGain_n}
{AverageLoss_n}
$$

$$
RSI=
100-\frac{100}{1+RS}
$$

Typical:

```text
RSI2
RSI5
RSI7
RSI14
RSI21
RSI50
```

---

# 10. RSI distance from thresholds

$$
RSIOverbought=
RSI-70
$$

$$
RSIOversold=
30-RSI
$$

You can create continuous rather than binary signals.

---

# 11. RSI slope

$$
RSISlope=
RSI_t-RSI_{t-k}
$$

## RSI acceleration

$$
RSIAcceleration=
\Delta RSI_t-\Delta RSI_{t-1}
$$

---

# 12. RSI divergence

Bullish divergence:

$$
\Delta Price<0
$$

while:

$$
\Delta RSI>0
$$

Bearish:

$$
\Delta Price>0
$$

while:

$$
\Delta RSI<0
$$

You can make divergence continuous:

$$
DivergenceScore=
Z(\Delta RSI)-Z(\Delta Price)
$$

---

# 13. Stochastic oscillator

$$
\%K=
100
\frac{C-L_n}
{H_n-L_n}
$$

$$
\%D=SMA(\%K,3)
$$

## Stochastic spread

$$
StochSpread=\%K-\%D
$$

## Stochastic slope

$$
StochSlope=
\%K_t-\%K_{t-k}
$$

---

# 14. Williams %R

$$
\%R=
-100
\frac{H_n-C}
{H_n-L_n}
$$

---

# 15. CCI

Typical price:

$$
TP=\frac{H+L+C}{3}
$$

Mean deviation:

$$
MD=
\frac{1}{n}
\sum|TP_i-SMA(TP)|
$$

CCI:

$$
CCI=
\frac{TP-SMA(TP)}
{0.015MD}
$$

---

# 16. ROC

$$
ROC_n=
\frac{C_t-C_{t-n}}
{C_{t-n}}\times100
$$

Calculate:

```text
ROC5
ROC10
ROC20
ROC60
ROC120
```

---

# 17. Momentum indicator

$$
Momentum_n=C_t-C_{t-n}
$$

Normalized:

$$
NormalizedMomentum=
\frac{C_t-C_{t-n}}
{ATR_n}
$$

---

# 18. Rate-of-change acceleration

$$
ROCAcceleration=
ROC_n(t)-ROC_n(t-k)
$$

---

# 19. Bollinger Bands

Middle:

$$
MB=SMA_n
$$

Upper:

$$
UB=MB+k\sigma_n
$$

Lower:

$$
LB=MB-k\sigma_n
$$

Normally:

$$
k=2
$$

---

# 20. Bollinger %B

$$
\%B=
\frac{C-LB}
{UB-LB}
$$

Interpretation:

* \(<0\): below lower band
* 0–1: inside bands
* \(>1\): above upper band

---

# 21. Bollinger bandwidth

$$
BBW=
\frac{UB-LB}
{MB}
$$

---

# 22. Bollinger bandwidth percentile

$$
BBWPercentile=
PercentileRank(BBW)
$$

This is useful for identifying volatility compression.

---

# 23. Bollinger squeeze

A basic squeeze condition:

$$
BBW<Percentile(BBW,p)
$$

For example:

$$
BBW<P_{20}
$$

Then:

$$
Squeeze=1
$$

---

# 24. Bollinger expansion

$$
BBWExpansion=
\frac{BBW_t}{BBW_{t-k}}-1
$$

---

# 25. Bollinger mean-reversion distance

$$
BBMeanDeviation=
\frac{C-MB}{UB-LB}
$$

---

# 26. ATR

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

ATR:

$$
ATR_n=SMA(TR,n)
$$

or Wilder smoothing.

---

# 27. Normalized ATR

$$
NATR=
100\frac{ATR_n}{C_t}
$$

---

# 28. ATR expansion

$$
ATRExpansion=
\frac{ATR_{short}}
{ATR_{long}}-1
$$

---

# 29. ATR contraction

$$
ATRContraction=
1-\frac{ATR_{short}}
{ATR_{long}}
$$

---

# 30. ATR-normalized movement

$$
ATRMove=
\frac{C_t-C_{t-n}}
{ATR_n}
$$

This is extremely useful for comparing technical moves across stocks.

---

# 31. ADX

Directional movement:

$$
+DM=
\begin{cases}
H_t-H_{t-1}, & H_t-H_{t-1}>L_{t-1}-L_t\\
0,&otherwise
\end{cases}
$$

$$
-DM=
\begin{cases}
L_{t-1}-L_t,&L_{t-1}-L_t>H_t-H_{t-1}\\
0,&otherwise
\end{cases}
$$

Then:

$$
+DI=
100\frac{Smoothed(+DM)}{ATR}
$$

$$
-DI=
100\frac{Smoothed(-DM)}{ATR}
$$

$$
DX=
100\frac{|+DI--DI|}
{+DI+-DI}
$$

$$
ADX=SMA(DX,n)
$$

---

# 32. Directional movement spread

$$
DIspread=
+DI--DI
$$

Normalized:

$$
DirectionalBias=
\frac{+DI--DI}
{+DI+-DI}
$$

---

# 33. ADX trend-strength score

A continuous trend-strength measure:

$$
TrendStrength=
f(ADX)
$$

Rather than simply:

$$
ADX>25
$$

use percentile:

$$
ADXPercentile=
PercentileRank(ADX)
$$

---

# 34. Parabolic SAR

SAR update:

$$
SAR_{t+1}
=
SAR_t+
AF(EP-SAR_t)
$$

where:

* \(AF\) = acceleration factor
* \(EP\) = extreme point

Signal:

$$
SARState=
I(C>SAR)
$$

Distance:

$$
SARGap=
\frac{C-SAR}{ATR}
$$

---

# 35. Ichimoku

Tenkan:

$$
Tenkan=
\frac{HH_9+LL_9}{2}
$$

Kijun:

$$
Kijun=
\frac{HH_{26}+LL_{26}}{2}
$$

Senkou A:

$$
SenkouA=
\frac{Tenkan+Kijun}{2}
$$

Senkou B:

$$
SenkouB=
\frac{HH_{52}+LL_{52}}{2}
$$

Chikou:

$$
Chikou=C_t
$$

shifted 26 periods backward.

---

# 36. Ichimoku cloud position

$$
CloudTop=\max(SenkouA,SenkouB)
$$

$$
CloudBottom=\min(SenkouA,SenkouB)
$$

Then:

$$
CloudPosition=
\frac{C-CloudBottom}
{CloudTop-CloudBottom}
$$

---

# 37. Cloud thickness

$$
CloudThickness=
|SenkouA-SenkouB|
$$

Normalize:

$$
CloudThicknessATR=
\frac{|SenkouA-SenkouB|}
{ATR}
$$

---

# 38. Pivot points

Classic pivot:

$$
P=\frac{H+L+C}{3}
$$

Resistance:

$$
R1=2P-L
$$

$$
R2=P+(H-L)
$$

$$
R3=H+2(P-L)
$$

Support:

$$
S1=2P-H
$$

$$
S2=P-(H-L)
$$

$$
S3=L-2(H-P)
$$

---

# 39. Pivot distance

$$
PivotGap=
\frac{C-P}{ATR}
$$

Likewise:

$$
R1Gap=\frac{R1-C}{ATR}
$$

$$
S1Gap=\frac{C-S1}{ATR}
$$

---

# 40. Support/resistance

## Rolling resistance

$$
Resistance_n=HighestHigh_n
$$

## Rolling support

$$
Support_n=LowestLow_n
$$

Distance:

$$
ResistanceDistance=
\frac{Resistance-C}{ATR}
$$

$$
SupportDistance=
\frac{C-Support}{ATR}
$$

---

# 41. Breakout

$$
BreakoutStrength=
\frac{C-HighestHigh_{n,t-1}}
{ATR}
$$

---

# 42. Breakdown

$$
BreakdownStrength=
\frac{LowestLow_{n,t-1}-C}
{ATR}
$$

---

# 43. Breakout persistence

After breakout:

$$
Persistence=
\frac{\text{days remaining above breakout level}}
{\text{observation window}}
$$

---

# 44. False breakout

A breakout followed by:

$$
C_t<BreakoutLevel
$$

within \(k\) periods.

Create:

$$
FalseBreakout=1
$$

or continuous:

$$
FalseBreakoutSeverity=
\frac{BreakoutLevel-C}
{ATR}
$$

---

# 45. Volume-confirmed breakout

$$
BreakoutConfirmation=
BreakoutStrength
\times
\frac{V_t}{AvgVolume_n}
$$

---

# 46. Price-volume divergence

Price:

$$
PTrend=Slope(C)
$$

Volume:

$$
VTrend=Slope(V)
$$

Then:

$$
PV_Divergence=PTrend-VTrend
$$

---

# 47. OBV

$$
OBV_t=
OBV_{t-1}
+
\begin{cases}
V_t&C_t>C_{t-1}\\
-V_t&C_t<C_{t-1}\\
0&C_t=C_{t-1}
\end{cases}
$$

---

# 48. OBV slope

$$
OBVSlope=
Slope(OBV,n)
$$

Normalize:

$$
OBVSlopeNorm=
\frac{OBVSlope}
{AvgVolume_n}
$$

---

# 49. OBV divergence

$$
OBVDivergence=
Momentum(OBV)-Momentum(C)
$$

---

# 50. Accumulation/Distribution

Money flow multiplier:

$$
MFM=
\frac{(C-L)-(H-C)}
{H-L}
$$

Money flow volume:

$$
MFV=MFM\times V
$$

A/D:

$$
AD_t=AD_{t-1}+MFV_t
$$

---

# 51. Chaikin Money Flow

$$
CMF_n=
\frac{\sum MFV}
{\sum Volume}
$$

---

# 52. Chaikin oscillator

$$
CO=
EMA_{3}(AD)-EMA_{10}(AD)
$$

---

# 53. Money Flow Index

$$
TP=\frac{H+L+C}{3}
$$

$$
MoneyFlow=TP\times V
$$

Then:

$$
MFI=
100-
\frac{100}{1+\frac{PositiveMoneyFlow}
{NegativeMoneyFlow}}
$$

---

# 54. VWAP

$$
VWAP=
\frac{\sum P_iV_i}
{\sum V_i}
$$

---

# 55. VWAP deviation

$$
VWAPGap=
\frac{C-VWAP}{VWAP}
$$

ATR normalized:

$$
VWAPGapATR=
\frac{C-VWAP}{ATR}
$$

---

# 56. Volume-weighted moving average

$$
VWMA_n=
\frac{\sum_{i=1}^{n}C_iV_i}
{\sum_{i=1}^{n}V_i}
$$

---

# 57. Relative volume

$$
RVOL=
\frac{V_t}
{SMA(V,n)}
$$

---

# 58. Volume spike

$$
VolumeSpike=
\frac{V_t}{Percentile_{95}(V,n)}
$$

---

# 59. Volume trend

$$
VolumeTrend=
\frac{SMA(V,20)}
{SMA(V,60)}-1
$$

---

# 60. Volume-price trend

A basic VPT formulation:

$$
VPT_t=
VPT_{t-1}
+
V_t
\left(
\frac{C_t-C_{t-1}}{C_{t-1}}
\right)
$$

---

# 61. Force Index

$$
FI=
(C_t-C_{t-1})V_t
$$

Smoothed:

$$
FI_n=EMA(FI,n)
$$

---

# 62. Ease of Movement

$$
EMV=
\frac{
(H_t+L_t)/2-(H_{t-1}+L_{t-1})/2
}
{Volume_t/(H_t-L_t)}
$$

---

# 63. Acceleration/deceleration

You can define generic indicator acceleration:

$$
Acceleration(X)=
(X_t-X_{t-k})-(X_{t-k}-X_{t-2k})
$$

Apply to:

```text
RSI
MACD
ROC
ADX
OBV
CMF
price
ATR
volume
```

---

# 64. Candlestick calculations

## Body

$$
Body=C-O
$$

## Body percentage

$$
BodyPct=
\frac{|C-O|}
{H-L}
$$

## Upper wick

$$
UpperWick=
H-\max(O,C)
$$

## Lower wick

$$
LowerWick=
\min(O,C)-L
$$

## Range

$$
Range=H-L
$$

---

# 65. Close location

$$
CLV=
\frac{(C-L)-(H-C)}
{H-L}
$$

Range:

$$
[-1,1]
$$

---

# 66. Intraday strength

$$
IntradayStrength=
\frac{C-L}{H-L}
$$

---

# 67. Gap

$$
Gap=
\frac{O-C_{t-1}}
{C_{t-1}}
$$

---

# 68. Gap continuation

$$
GapContinuation=
Sign(O-C_{t-1})
\times
Sign(C-O)
$$

---

# 69. Gap fill

For an upward gap:

$$
GapFill=
\frac{C_{t-1}-L_t}
{O_t-C_{t-1}}
$$

---

# 70. Higher-high / lower-high structure

Define:

$$
HH=I(H_t>H_{t-k})
$$

$$
LH=I(H_t<H_{t-k})
$$

Likewise:

$$
HL=I(L_t>L_{t-k})
$$

$$
LL=I(L_t<L_{t-k})
$$

Then:

$$
StructureScore=
HH+HL-LH-LL
$$

---

# 71. Swing-high / swing-low structure

Identify local extrema:

$$
SwingHigh_t=
I(H_t>H_{t-k:t+k})
$$

$$
SwingLow_t=
I(L_t<L_{t-k:t+k})
$$

Then calculate:

* higher highs
* higher lows
* lower highs
* lower lows

This is one of the better ways to quantify price structure.

---

# 72. Trend structure

For a bullish trend:

$$
HH+HL
$$

For bearish:

$$
LH+LL
$$

A continuous trend-structure score:

$$
TrendStructure=
\frac{HH+HL-LH-LL}{N}
$$

---

# 73. Linear regression trend

Fit:

$$
P_t=\alpha+\beta t+\epsilon_t
$$

Technical trend:

$$
TrendSlope=\beta
$$

Normalize:

$$
TrendSlopePct=
\frac{\beta}{Mean(P)}
$$

---

# 74. Regression \(R^2\)

$$
R^2=
1-\frac{SS_{res}}{SS_{tot}}
$$

High \(R^2\):

> cleaner trend

Low \(R^2\):

> noisy trend

---

# 75. Trend quality

Combine:

$$
TrendQuality=
Sign(\beta)\times R^2
$$

This is substantially more useful than simply saying:

> price is above SMA200.

---

# 76. Linear regression channel

Predicted price:

$$
\hat P_t=\alpha+\beta t
$$

Residual:

$$
e_t=P_t-\hat P_t
$$

Residual z-score:

$$
Z_{residual}=
\frac{e_t}{Std(e)}
$$

---

# 77. Regression-channel position

$$
ChannelPosition=
\frac{P-LowerChannel}
{UpperChannel-LowerChannel}
$$

---

# 78. Efficiency ratio

$$
ER=
\frac{|C_t-C_{t-n}|}
{\sum_{i=1}^{n}|C_i-C_{i-1}|}
$$

Near 1:

> efficient directional trend

Near 0:

> noisy market

---

# 79. Trend-to-noise ratio

$$
TNR=
\frac{|C_t-C_{t-n}|}
{\sigma(C)}
$$

---

# 80. Price z-score

$$
ZPrice=
\frac{C-SMA_n}
{Std(C,n)}
$$

---

# 81. Return z-score

$$
ZReturn=
\frac{R_t-\mu_R}
{\sigma_R}
$$

---

# 82. Mean-reversion score

A simple continuous construction:

$$
MRScore=
-w_1ZPrice
-w_2RSI_Z
-w_3ROC_Z
$$

The sign depends on whether you're scoring **reversion opportunity** or **current trend quality**.

This distinction matters enormously.

---

# 83. Autocorrelation

$$
\rho_k=
Corr(r_t,r_{t-k})
$$

Calculate:

$$
ACF_1,ACF_5,ACF_{20}
$$

Positive:

> persistence

Negative:

> reversal

---

# 84. Variance ratio

$$
VR(k)=
\frac{Var(r^{(k)})}
{kVar(r)}
$$

Useful for identifying:

* trend
* random walk
* mean reversion

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

persistence.

$$
H<0.5
$$

anti-persistence.

$$
H\approx0.5
$$

random-walk-like.

Use cautiously because different estimators can produce materially different values.

---

# 86. Fractal dimension

A commonly used relationship:

$$
D\approx2-H
$$

Useful as a secondary trend/complexity measure.

---

# 87. Volatility

Rolling standard deviation:

$$
\sigma_n=
Std(r_{t-n:t})
$$

Annualized:

$$
\sigma_{annual}
=
\sigma_n\sqrt{252}
$$

---

# 88. Downside volatility

$$
\sigma_{down}
=
Std(\min(r,0))
$$

---

# 89. Volatility percentile

$$
VolPercentile=
PercentileRank(\sigma_n)
$$

---

# 90. Volatility regime

$$
VolRegime=
\frac{\sigma_{short}}
{\sigma_{long}}
$$

---

# 91. Volatility acceleration

$$
VolAcceleration=
VolRegime_t-VolRegime_{t-k}
$$

---

# 92. Range volatility

$$
RangeVol=
Std(H-L)
$$

---

# 93. Parkinson volatility

Using high/low data:

$$
\sigma_P=
\sqrt{
\frac{1}{4n\ln2}
\sum_{i=1}^{n}
\left(
\ln\frac{H_i}{L_i}
\right)^2
}
$$

Annualized:

$$
\sigma_{P,annual}=\sigma_P\sqrt{252}
$$

---

# 94. Garman-Klass volatility

$$
\sigma_{GK}^2=
\frac{1}{n}
\sum
\left[
\frac12
\left(\ln\frac{H}{L}\right)^2
-
(2\ln2-1)
\left(\ln\frac{C}{O}\right)^2
\right]
$$

---

# 95. Rogers-Satchell volatility

$$
\sigma_{RS}^2=
\frac1n
\sum
\left[
\ln\frac{H}{C}
\ln\frac{H}{O}
+
\ln\frac{L}{C}
\ln\frac{L}{O}
\right]
$$

These are useful if your technical engine has OHLC data but return volatility alone is insufficient.

---

# 96. Range expansion

$$
RangeExpansion=
\frac{H-L}
{SMA(H-L,n)}
$$

---

# 97. ATR percentile

$$
ATRPercentile=
PercentileRank(ATR\%)
$$

---

# 98. Drawdown

$$
DD_t=
\frac{C_t}{RollingMax(C_t)}-1
$$

---

# 99. Maximum drawdown

$$
MDD=
\min_t DD_t
$$

---

# 100. Drawdown recovery

$$
Recovery=
\frac{C_t-Trough}
{Peak-Trough}
$$

---

# 101. Time since high

$$
HighAge=
t-t_{lastHigh}
$$

---

# 102. Distance from high

$$
HighDistance=
\frac{C_t}{High_n}-1
$$

---

# 103. Distance from low

$$
LowDistance=
\frac{C_t}{Low_n}-1
$$

---

# 104. Position within range

$$
RangePosition=
\frac{C-Low_n}
{High_n-Low_n}
$$

---

# 105. Pivot structure

Beyond classic pivots, calculate:

$$
DistanceToR1,\ DistanceToR2,\ DistanceToS1,\ DistanceToS2
$$

all normalized by ATR.

---

# 106. Fibonacci retracement

For swing high \(H\) and low \(L\):

$$
Fib_{23.6}=H-0.236(H-L)
$$

$$
Fib_{38.2}=H-0.382(H-L)
$$

$$
Fib_{50}=H-0.5(H-L)
$$

$$
Fib_{61.8}=H-0.618(H-L)
$$

$$
Fib_{78.6}=H-0.786(H-L)
$$

Then calculate price distance to each level.

I'd keep Fibonacci signals relatively low-weight because the swing-point definition can be subjective.

---

# 107. Donchian channels

Upper:

$$
DCUpper_n=HighestHigh_n
$$

Lower:

$$
DCLower_n=LowestLow_n
$$

Middle:

$$
DCMiddle=
\frac{DCUpper+DCLower}{2}
$$

Position:

$$
DCPosition=
\frac{C-DCLower}
{DCUpper-DCLower}
$$

---

# 108. Keltner Channels

Typical:

$$
Middle=EMA_n
$$

$$
Upper=EMA_n+kATR_n
$$

$$
Lower=EMA_n-kATR_n
$$

Then:

$$
KCPosition=
\frac{C-Lower}
{Upper-Lower}
$$

---

# 109. Keltner/Bollinger squeeze

A squeeze can be defined when:

$$
BBUpper<KCUpper
$$

and:

$$
BBLower>KCLower
$$

This identifies Bollinger Bands contracting inside Keltner Channels.

---

# 110. TTM-style squeeze momentum

You can combine:

$$
SqueezeState
$$

with:

$$
MomentumHistogram
$$

to distinguish:

* compression + bullish expansion
* compression + bearish expansion
* compression without directional confirmation

---

# 111. Aroon

$$
AroonUp=
100\frac{n-DaysSinceHighestHigh}{n}
$$

$$
AroonDown=
100\frac{n-DaysSinceLowestLow}{n}
$$

Aroon oscillator:

$$
AroonOsc=
AroonUp-AroonDown
$$

---

# 112. TRIX

Triple-smoothed EMA:

$$
EMA_1=EMA(C)
$$

$$
EMA_2=EMA(EMA_1)
$$

$$
EMA_3=EMA(EMA_2)
$$

Then:

$$
TRIX=
\frac{EMA_{3,t}-EMA_{3,t-1}}
{EMA_{3,t-1}}
$$

---

# 113. DPO

Detrended Price Oscillator:

$$
DPO=
C_t-SMA(C,n)
$$

with the traditional time shift depending on implementation.

---

# 114. Ultimate Oscillator

For three periods:

$$
BP=C-L_{prev}
$$

$$
TR=\max(H,C_{prev})-\min(L,C_{prev})
$$

Then:

$$
UO=
100
\frac{
4Avg_7(BP/TR)
+2Avg_{14}(BP/TR)
+Avg_{28}(BP/TR)
}{7}
$$

---

# 115. Awesome Oscillator

$$
MedianPrice=\frac{H+L}{2}
$$

$$
AO=SMA_5(MedianPrice)-SMA_{34}(MedianPrice)
$$

---

# 116. Relative Vigor Index

A simplified RVI:

$$
RVI=
\frac{SMA(C-O,n)}
{SMA(H-L,n)}
$$

with signal line:

$$
RVI_{signal}=SMA(RVI,4)
$$

---

# 117. Coppock Curve

$$
Coppock=
WMA_{10}
(
ROC_{14}+ROC_{11}
)
$$

Useful for long-term momentum.

---

# 118. Know Sure Thing

KST combines multiple smoothed ROC measures:

$$
KST=
w_1ROC_1+
w_2ROC_2+
w_3ROC_3+
w_4ROC_4
$$

with smoothing applied to each component.

---

# 119. Technical breadth

If calculating technical conditions across a stock universe:

$$
PctAboveSMA50=
\frac{\#(C>SMA50)}
{N}
$$

$$
PctAboveSMA200=
\frac{\#(C>SMA200)}
{N}
$$

This arguably belongs in MarketScore rather than TechnicalScore, but can be useful as a market confirmation input.

---

# 120. Technical breadth thrust

$$
BreadthThrust=
\frac{AdvancingStocks}
{AdvancingStocks+DecliningStocks}
$$

---

# 121. New-high/new-low technical breadth

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

Again, I'd generally feed this to **MarketScore/RegimeScore**, not the individual stock's TechnicalScore.

---

# 122. Relative technical strength

Compare technical score against sector:

$$
RelativeTechnical=
TechnicalMetric_{stock}
-
Median(TechnicalMetric_{sector})
$$

---

# 123. Technical factor normalization

This is where the raw indicator library becomes a useful quantitative score.

For each indicator:

$$
Z_i=
\frac{X_i-\mu_X}{\sigma_X}
$$

or:

$$
Percentile_i=
PercentileRank(X_i)
$$

Then transform to:

$$
Score_i=100\times Percentile_i
$$

For an inverse indicator:

$$
Score_i=
100(1-Percentile_i)
$$

---

# 124. Sector-relative technical normalization

For example:

$$
RSI_{relative}=
RSI_{stock}
-
Median(RSI_{sector})
$$

Likewise for:

* volatility
* trend slope
* momentum
* ATR
* distance from MA
* breakout strength

This helps prevent comparing a naturally volatile semiconductor with a low-volatility utility using identical raw thresholds.

---

# 125. Technical subscores

I would organize the indicators into approximately these groups:

### Trend

$$
TrendScore=
f(
MAAlignment,
MASlope,
MACD,
ADX,
Ichimoku,
RegressionTrend,
TrendStructure
)
$$

### Momentum

$$
MomentumScore=
f(
RSI,
ROC,
Momentum,
Stochastic,
MACDHistogram,
TRIX,
Coppock
)
$$

### Volatility

$$
VolatilityScore=
f(
ATR,
NATR,
BBWidth,
VolatilityPercentile,
RangeExpansion
)
$$

### Support/resistance

$$
SRScore=
f(
DistanceToSupport,
DistanceToResistance,
Breakout,
Breakdown,
PivotPosition,
DonchianPosition
)
$$

### Volume/confirmation

$$
VolumeScore=
f(
RVOL,
OBV,
CMF,
AD,
VPT,
ForceIndex
)
$$

### Mean reversion

$$
MRScore=
f(
RSI,
ZPrice,
BBPosition,
DistanceToMA,
Autocorrelation
)
$$

### Price structure

$$
StructureScore=
f(
HH,
HL,
LH,
LL,
SwingStructure,
RegressionTrend
)
$$

### Setup quality

$$
SetupScore=
f(
Trend,
Momentum,
Volatility,
VolumeConfirmation,
SupportResistance
)
$$

---

# 126. Composite TechnicalScore

Then:

$$
TechnicalScore=
w_TTrendScore+
w_MMomentumScore+
w_VVolatilityScore+
w_{SR}SRScore+
w_{Vol}VolumeScore+
w_{MR}MeanReversionScore+
w_StructureStructureScore+
w_{Setup}SetupScore
$$

For an initial research configuration, you could test:

| Component           | Initial weight |
| ------------------- | -------------: |
| Trend               |            20% |
| Momentum            |            20% |
| Volatility          |            10% |
| Support/Resistance  |            15% |
| Volume Confirmation |            10% |
| Mean Reversion      |            10% |
| Price Structure     |            10% |
| Setup Quality       |             5% |
| **Total**           |       **100%** |

Again, these should be treated as **backtest parameters**, not universal optimal weights.

---

# 127. Important: don't let TechnicalScore become 100 indicators voting independently

This is probably the most important point for your implementation.

Suppose you calculate:

```text
RSI
Stochastic
Williams %R
CCI
MFI
Ultimate Oscillator
```

Those are **not six independent pieces of information**.

They all substantially measure variations of:

> price position / momentum / overbought-oversold behavior.

Likewise:

```text
SMA20
EMA20
WMA20
HMA20
MACD
MACD signal
```

are strongly related.

Therefore your architecture should be:

```text
RAW INDICATORS
       ↓
CORRELATION / REDUNDANCY CONTROL
       ↓
INDICATOR CLUSTERS
       ↓
SUBSCORES
       ↓
TECHNICAL SCORE
```

---

# 128. Recommended indicator clusters

I'd use approximately:

```text
Cluster 1 — Trend
    SMA/EMA alignment
    MA slopes
    MACD
    ADX
    Ichimoku
    Regression slope/R²

Cluster 2 — Momentum
    RSI
    ROC
    Momentum
    Stochastic
    Williams %R
    CCI

Cluster 3 — Volatility
    ATR
    NATR
    Bollinger width
    realized volatility
    range expansion

Cluster 4 — Price Structure
    HH/HL
    LH/LL
    swing highs/lows
    support/resistance
    breakouts
    breakdowns

Cluster 5 — Volume Confirmation
    RVOL
    OBV
    CMF
    A/D
    VPT
    Force Index

Cluster 6 — Mean Reversion
    price z-score
    Bollinger %B
    MA deviation
    RSI extremes
    short-term autocorrelation

Cluster 7 — Setup Quality
    trend + momentum
    trend + volume
    breakout + volume
    volatility + breakout
    support + reversal
```

Then:

$$
TechnicalScore=
\sum_{k=1}^{7}
w_kClusterScore_k
$$

---

# 129. A particularly useful addition: Technical State

I would actually have your engine output **two things**, not one:

### TechnicalScore

"What is the current technical condition?"

and:

### TechnicalState

```text
STRONG_UPTREND
UPTREND
WEAK_UPTREND
NEUTRAL
WEAK_DOWNTREND
DOWNTREND
STRONG_DOWNTREND
```

The state can be derived deterministically from continuous factors.

For example:

$$
TrendState=
f(
MAAlignment,
MASlope,
ADX,
MACD,
Structure
)
$$

This is more useful to your LLM than simply:

```text
TechnicalScore = 73
```

---

# 130. Technical acceleration

For your system specifically, I'd also add:

$$
TechnicalAcceleration=
TechnicalScore_t-
TechnicalScore_{t-n}
$$

and:

$$
TechnicalJerk=
TechnicalAcceleration_t-
TechnicalAcceleration_{t-n}
$$

That gives you:

```text
TechnicalScore       = 72
TechnicalAcceleration = +11
```

versus:

```text
TechnicalScore       = 82
TechnicalAcceleration = -14
```

Those two stocks have very different technical states despite similar current scores.

---

# 131. Technical disagreement

You can calculate dispersion among the major technical clusters:

$$
TechnicalDispersion=
Std(
TrendScore,
MomentumScore,
VolumeScore,
VolatilityScore,
StructureScore
)
$$

Then:

$$
TechnicalAgreement=
1-NormalizedDispersion
$$

This is particularly useful for your LLM architecture.

For example:

```text
TechnicalScore:      78
TechnicalAgreement:  91%
```

means most technical evidence agrees.

Whereas:

```text
TechnicalScore:      78
TechnicalAgreement:  43%
```

means the composite hides a significant disagreement.

---

# 132. Technical coverage

Just like your FundamentalScore:

$$
Coverage=
\frac{
\sum_i w_iAvailable_i
}{
\sum_iw_i
}
$$

Then output:

```text
TechnicalScore:       78
TechnicalCoverage:    94%
TechnicalAgreement:   87%
TechnicalConfidence:  91%
```

Keep these separate.

**Do not automatically multiply:**

$$
78\times0.94
$$

unless you have deliberately decided that missing data should mathematically penalize the score.

---

# 133. My recommended TechnicalScore architecture for your system

Given your existing TradingAgents/quant-engine design, I'd use:

```text
                         TECHNICAL ENGINE
                                │
        ┌───────────────────────┼────────────────────────┐
        │                       │                        │
      TREND                  MOMENTUM                STRUCTURE
        │                       │                        │
   MA alignment              RSI                     HH/HL
   MA slope                 ROC                     LH/LL
   MACD                     Stoch                   Swings
   ADX                      CCI                     S/R
   Ichimoku                 Williams %R             Breakouts
   Regression               TRIX                    Breakdown
        │                       │                        │
        └───────────────┬───────┴───────────┬────────────┘
                        │                   │
                    VOLATILITY          VOLUME/FLOW
                        │                   │
                      ATR                 OBV
                    NATR                  CMF
                   BBWidth                 A/D
                  BB squeeze               VPT
                  Range expansion          RVOL
                        │                   │
                        └─────────┬─────────┘
                                  │
                         MEAN REVERSION
                                  │
                           Z-score
                           BB %B
                           MA deviation
                           RSI extremes
                           Autocorrelation
                                  │
                                  ▼
                        INDICATOR CLUSTERING
                                  │
                                  ▼
                           NORMALIZATION
                                  │
                                  ▼
                          TECHNICAL SUBSCORES
                                  │
                                  ▼
                         ┌─────────────────┐
                         │ TechnicalScore  │
                         └─────────────────┘
                            │           │
                       Coverage      Agreement
                            │           │
                            └─────┬─────┘
                                  ▼
                         TechnicalConfidence
```

---

## The clean boundary I'd use across your engines

This is especially important given the **FundamentalScore + MarketScore + TechnicalScore + RegimeScore + RiskScore** architecture you've been building:

| Engine               | Primary question                                               |
| -------------------- | -------------------------------------------------------------- |
| **FundamentalScore** | Is the business financially strong/weak?                       |
| **MarketScore**      | How is this security behaving relative to the market/universe? |
| **TechnicalScore**   | What is the current price/technical setup?                     |
| **RegimeScore**      | What market/macro regime are we in?                            |
| **RiskScore**        | What can go wrong and how severe is the exposure?              |
| **NewsScore**        | What does current news imply?                                  |
| **SentimentScore**   | What is the current sentiment state?                           |
| **EventScore**       | Are upcoming/ongoing events changing the setup?                |
| **TradeScore**       | What does the integrated evidence say about the trade?         |

That separation is much cleaner than allowing every engine to calculate RSI, momentum, volatility, beta, market trend, etc.

### One final recommendation

For your implementation, I would **not actually implement every formula above as a first-class score input**. I would implement perhaps **50–70 raw technical calculations**, but collapse them into roughly **7–8 independent technical factors**:

$$
\boxed{
TechnicalScore=
w_1Trend+
w_2Momentum+
w_3Structure+
w_4Volume+
w_5Volatility+
w_6MeanReversion+
w_7BreakoutSetup+
w_8TechnicalAcceleration
}
$$

Then expose the underlying calculations in the deterministic report for transparency.

That gives your LLM something much more useful than 100 indicator numbers:

```text
TechnicalScore:             74.8
TrendScore:                 82.1
MomentumScore:              77.4
StructureScore:             80.6
VolumeConfirmationScore:    71.2
VolatilityScore:            58.9
MeanReversionScore:         46.3
BreakoutSetupScore:         79.8
TechnicalAcceleration:     +12.4

Coverage:                   96%
FactorAgreement:            84%
Confidence:                 89%

Primary technical state:
    Bullish intermediate trend
    Positive momentum
    Strong price structure
    Volume confirms trend
    Short-term overextension present
    Volatility expanding
```

That last representation is much more compatible with the **compact decision-context architecture** you've been developing: the deterministic engine performs the enormous amount of calculation, while the LLM receives the **compressed technical evidence and its provenance**, rather than having to rediscover the technical interpretation from dozens of raw indicators.
