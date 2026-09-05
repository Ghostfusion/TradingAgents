Absolutely. For your **12-ETF sector-ranking system**, I would build the score as a multi-factor model rather than relying on one indicator.

The universe is:

`XLK, SOXX, XLC, XLY, XLP, XLE, XLF, XLV, XLI, XLB, XLRE, XLU`

Below is a fairly complete framework you can implement directly in a quantitative research application.

---

# 1. Overall architecture

I recommend a **100-point sector score**:

$$
Score_i =
0.25M_i+
0.15RS_i+
0.10T_i+
0.15R_i+
0.10V_i+
0.10B_i+
0.10F_i+
0.05Q_i
$$

where:

* \(M\) = Momentum
* \(RS\) = Relative Strength
* \(T\) = Trend
* \(R\) = Risk-adjusted performance
* \(V\) = Valuation
* \(B\) = Breadth
* \(F\) = Flow/volume
* \(Q\) = Quality/fundamental confirmation

For a **pure ETF technical-rotation system**, I'd reduce valuation/fundamentals and increase momentum/trend.

---

# 2. Price return calculations

For ETF \(i\):

$$
R_{i,n}=\frac{P_t}{P_{t-n}}-1
$$

Calculate:

* 5-day
* 21-day
* 63-day
* 126-day
* 252-day

So:

$$
R_{21}=\frac{P_t}{P_{t-21}}-1
$$

$$
R_{63}=\frac{P_t}{P_{t-63}}-1
$$

$$
R_{126}=\frac{P_t}{P_{t-126}}-1
$$

$$
R_{252}=\frac{P_t}{P_{t-252}}-1
$$

For sector rotation, I'd give the greatest weight to **3–12 month momentum**.

---

# 3. Momentum score

A good composite:

$$
M =
0.10R_{21}
+0.30R_{63}
+0.30R_{126}
+0.30R_{252}
$$

However, raw returns shouldn't be compared directly because different periods have different distributions.

Instead, cross-sectionally normalize them.

### Percentile normalization

For each ETF:

$$
M_{63}^{pct}
=
PercentileRank(R_{63})
$$

Then:

$$
M =
0.10M_{21}^{pct}
+0.30M_{63}^{pct}
+0.30M_{126}^{pct}
+0.30M_{252}^{pct}
$$

This produces a 0–100 score.

---

# 4. Risk-adjusted momentum

Raw momentum can favor extremely volatile ETFs.

Calculate:

$$
M_{risk}=\frac{R_{126}}{\sigma_{126}}
$$

where:

$$
\sigma_{126}
=
StdDev(r_1,\ldots,r_{126})\sqrt{252}
$$

Then cross-sectional percentile rank:

$$
MRS_i=PercentileRank(M_{risk,i})
$$

This is especially useful for comparing **SOXX against XLK**, because SOXX can generate enormous returns but also much larger drawdowns.

---

# 5. Relative strength versus SPY

This is one of the most important calculations.

Let:

$$
RS_t=\frac{P_{ETF,t}}{P_{SPY,t}}
$$

Then calculate the return of that ratio:

$$
RSR_{63}
=
\frac{RS_t}{RS_{t-63}}-1
$$

Likewise:

$$
RSR_{126}
=
\frac{RS_t}{RS_{t-126}}-1
$$

$$
RSR_{252}
=
\frac{RS_t}{RS_{t-252}}-1
$$

Composite:

$$
RS=
0.20Pct(RSR_{21})
+0.35Pct(RSR_{63})
+0.30Pct(RSR_{126})
+0.15Pct(RSR_{252})
$$

### Interpretation

If:

$$
RSR_{126}>0
$$

the sector has outperformed SPY over six months.

If:

$$
RSR_{126}<0
$$

the sector is underperforming the market.

This is much more useful than simply asking whether the ETF went up.

---

# 6. Trend score

Use multiple moving averages.

Calculate:

$$
SMA_{20}, SMA_{50}, SMA_{100}, SMA_{200}
$$

and:

$$
EMA_{20}, EMA_{50}
$$

### Price position

$$
P20=\frac{P_t}{SMA_{20}}-1
$$

$$
P50=\frac{P_t}{SMA_{50}}-1
$$

$$
P200=\frac{P_t}{SMA_{200}}-1
$$

### Moving-average alignment

Give points:

```text
Price > SMA20       +1
SMA20 > SMA50       +1
SMA50 > SMA100      +1
SMA100 > SMA200     +1
Price > SMA200      +1
```

Maximum:

$$
TrendScore=100
$$

if all five conditions are satisfied.

---

# 7. Moving-average slope

Don't just determine whether price is above an MA.

Determine whether the MA itself is rising.

For example:

$$
Slope_{50}=
\frac{SMA_{50,t}}{SMA_{50,t-20}}-1
$$

and:

$$
Slope_{200}=
\frac{SMA_{200,t}}{SMA_{200,t-60}}-1
$$

Then:

```text
50-day MA rising       positive
200-day MA rising      positive
both rising            strong bullish signal
both falling           bearish signal
```

---

# 8. RSI

Calculate 14-day RSI:

$$
RS=\frac{AverageGain_{14}}{AverageLoss_{14}}
$$

$$
RSI=100-\frac{100}{1+RS}
$$

Don't automatically treat RSI >70 as bearish.

For **momentum investing**, an ETF with RSI 65–75 while maintaining strong relative strength can be extremely healthy.

I'd score RSI approximately:

$$
RSIScore=
\begin{cases}
20 & RSI<30\\
60 & 30\le RSI<45\\
90 & 45\le RSI<60\\
100 & 60\le RSI<70\\
80 & 70\le RSI<80\\
40 & RSI\ge80
\end{cases}
$$

The purpose is to identify **healthy momentum**, not simply oversold conditions.

---

# 9. MACD

Standard:

$$
MACD=EMA_{12}-EMA_{26}
$$

Signal:

$$
Signal=EMA_9(MACD)
$$

Histogram:

$$
Histogram=MACD-Signal
$$

Useful signals:

```text
MACD > Signal             bullish
MACD < Signal             bearish
MACD > 0                 strong
MACD < 0                 weak
Histogram increasing      momentum accelerating
Histogram decreasing      momentum weakening
```

You can construct:

$$
MACDScore=
25I(MACD>0)
+25I(MACD>Signal)
+25I(Histogram>0)
+25I(\Delta Histogram>0)
$$

---

# 10. Bollinger Bands

Calculate:

$$
Middle=SMA_{20}
$$

$$
Upper=SMA_{20}+2\sigma_{20}
$$

$$
Lower=SMA_{20}-2\sigma_{20}
$$

Bollinger %B:

$$
\%B=
\frac{P-Lower}{Upper-Lower}
$$

Bandwidth:

$$
BBW=
\frac{Upper-Lower}{Middle}
$$

Use BBW primarily to identify volatility compression/expansion.

A useful signal:

$$
BBW_{expansion}=
\frac{BBW_t}{BBW_{t-20}}-1
$$

Positive expansion + positive momentum can be an excellent breakout confirmation.

---

# 11. Volatility

Calculate daily logarithmic returns:

$$
r_t=\ln\left(\frac{P_t}{P_{t-1}}\right)
$$

Annualized volatility:

$$
\sigma=
StdDev(r_t)\sqrt{252}
$$

Calculate:

* 21-day volatility
* 63-day volatility
* 126-day volatility
* 252-day volatility

Composite:

$$
Vol=
0.20\sigma_{21}
+0.30\sigma_{63}
+0.30\sigma_{126}
+0.20\sigma_{252}
$$

Because **lower volatility isn't automatically better**, I'd use volatility mainly as a risk adjustment rather than directly rewarding low volatility.

---

# 12. Sharpe ratio

For period \(T\):

$$
Sharpe=
\frac{R_p-R_f}{\sigma_p}
$$

For daily returns:

$$
Sharpe=
\frac{\bar r-r_f/252}{\sigma_r}\sqrt{252}
$$

Calculate:

* 63-day Sharpe
* 126-day Sharpe
* 252-day Sharpe

Composite:

$$
SharpeScore=
0.25Pct(Sharpe_{63})
+0.35Pct(Sharpe_{126})
+0.40Pct(Sharpe_{252})
$$

---

# 13. Sortino ratio

Sharpe penalizes upside and downside volatility equally.

Sortino only penalizes downside.

$$
Sortino=
\frac{R_p-R_f}{DownsideDeviation}
$$

where:

$$
DownsideDeviation=
\sqrt{
\frac{\sum \min(0,r_t-r_{target})^2}{N}
}
$$

For sector rotation, I actually prefer **Sortino over Sharpe**.

---

# 14. Maximum drawdown

Calculate running maximum:

$$
Peak_t=\max(P_1,\ldots,P_t)
$$

Drawdown:

$$
DD_t=\frac{P_t-Peak_t}{Peak_t}
$$

Maximum drawdown:

$$
MDD=\min(DD_t)
$$

Calculate:

* 63-day MDD
* 126-day MDD
* 252-day MDD
* 3-year MDD

Then:

$$
DrawdownScore=100\times
\left(1-\frac{|MDD_i|}{Max(|MDD|)}\right)
$$

or, preferably, percentile rank the drawdowns cross-sectionally.

---

# 15. Recovery strength

A sector that suffers a large drawdown but recovers quickly is different from one that remains depressed.

Calculate:

$$
Recovery=
\frac{P_t}{Peak_{previous}}-1
$$

and:

$$
RecoveryVelocity=
\frac{Return_{recovery}}{Days_{recovery}}
$$

You can also measure:

**Days from trough to new high.**

Lower is better.

---

# 16. Distance from 52-week high

$$
D_{52H}=
\frac{P_t}{High_{252}}-1
$$

Example:

$$
D_{52H}=-0.03
$$

means the ETF is 3% below its 52-week high.

This is particularly useful for distinguishing:

**strong pullback**

from

**broken trend**.

---

# 17. 52-week high breakout

Binary:

$$
Breakout=I(P_t>High_{252,prior})
$$

More useful:

$$
BreakoutStrength=
\frac{P_t-High_{252,prior}}{ATR_{14}}
$$

So a breakout 2 ATR above the previous high is much more meaningful than a marginal breakout.

---

# 18. ATR

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

Then:

$$
ATR_{14}=SMA_{14}(TR)
$$

Normalized ATR:

$$
NATR=
\frac{ATR_{14}}{P_t}
$$

This allows you to compare volatility between ETFs with different prices.

---

# 19. Volume confirmation

Volume ratio:

$$
VR_{20}=
\frac{Volume_t}{SMA_{20}(Volume)}
$$

More robust:

$$
VR_{5/20}=
\frac{SMA_5(Volume)}
{SMA_{20}(Volume)}
$$

Momentum + increasing volume is stronger than momentum without volume confirmation.

---

# 20. Dollar volume / liquidity

Calculate:

$$
DollarVolume=Price\times Volume
$$

Then:

$$
ADV_{20}=
SMA_{20}(DollarVolume)
$$

For an institutional-quality ranking system, liquidity should be a **hard eligibility filter**, not necessarily a scoring factor.

---

# 21. OBV

On-Balance Volume:

$$
OBV_t=
\begin{cases}
OBV_{t-1}+V_t & P_t>P_{t-1}\\
OBV_{t-1}-V_t & P_t<P_{t-1}\\
OBV_{t-1} & P_t=P_{t-1}
\end{cases}
$$

Then:

$$
OBVTrend=
\frac{OBV_t}{SMA_{20}(OBV)}-1
$$

Positive OBV trend supports accumulation.

---

# 22. Money Flow Index

Typical price:

$$
TP=\frac{H+L+C}{3}
$$

Raw money flow:

$$
RMF=TP\times Volume
$$

Then calculate positive and negative money flow over 14 periods.

$$
MFR=
\frac{PositiveMF}{NegativeMF}
$$

$$
MFI=
100-\frac{100}{1+MFR}
$$

---

# 23. Sector breadth

This is extremely important if you're ranking **sector ETFs**.

Don't only examine the ETF price.

Look at the stocks inside it.

For sector \(S\):

$$
Breadth_{50}=
\frac{\#Stocks(P>SMA_{50})}
{\#Stocks}
$$

Likewise:

$$
Breadth_{200}=
\frac{\#Stocks(P>SMA_{200})}
{\#Stocks}
$$

Example:

```text
SOXX

30 stocks
24 above 50-day MA

Breadth50 = 24/30 = 80%
```

That's a much healthier semiconductor rally than one driven by only NVIDIA.

---

# 24. Advance/decline breadth

For each stock:

$$
A_t=
\begin{cases}
+1 & R_t>0\\
-1 & R_t<0\\
0 & R_t=0
\end{cases}
$$

Then:

$$
AD_t=AD_{t-1}+\sum A_t
$$

Calculate the slope of the sector A/D line.

---

# 25. Equal-weight vs cap-weighted relative strength

This is an especially powerful factor for your system.

Compare the normal sector ETF with an equal-weight version.

For example:

$$
LeadershipRatio=
\frac{SectorCapWeighted}
{SectorEqualWeighted}
$$

If cap-weighted performance is dramatically better than equal-weighted performance, the sector may be dependent on a handful of mega-cap stocks.

That's important for **SOXX**, where semiconductor performance can become concentrated.

---

# 26. Correlation to SPY

$$
\rho_i=
Corr(r_i,r_{SPY})
$$

Calculate:

* 21-day
* 63-day
* 126-day
* 252-day

This tells you whether the sector is providing genuine diversification or simply behaving like the market.

---

# 27. Beta

$$
\beta_i=
\frac{Cov(r_i,r_m)}
{Var(r_m)}
$$

where \(r_m\) is SPY return.

Then:

$$
Alpha_i=
R_i-R_f-\beta_i(R_m-R_f)
$$

Positive alpha is desirable.

---

# 28. Downside beta

Standard beta isn't enough.

Calculate:

$$
\beta_{down}=
\frac{Cov(r_i,r_m\mid r_m<0)}
{Var(r_m\mid r_m<0)}
$$

This tells you how badly the sector behaves **when the market falls**.

Very useful for risk management.

---

# 29. Regime filter

Before ranking sectors, classify the overall market.

For SPY:

### Bull regime

$$
SPY>SMA_{200}
$$

and:

$$
Slope(SMA_{200})>0
$$

### Bear regime

$$
SPY<SMA_{200}
$$

and:

$$
Slope(SMA_{200})<0
$$

### Transitional regime

Everything else.

Then change sector weights according to regime.

---

# 30. Volatility regime

Use VIX or SPY realized volatility.

For realized volatility:

$$
RV_{20}=StdDev(r_{SPY,20})\sqrt{252}
$$

Define:

```text
Low volatility
Normal volatility
High volatility
Extreme volatility
```

In high-volatility regimes, increase the importance of:

* Sortino
* drawdown
* downside beta
* trend
* volatility

and decrease the importance of raw momentum.

---

# 31. Momentum acceleration

This is particularly useful for catching sectors **before they become obvious**.

$$
Accel=
R_{63}-R_{126}/2
$$

A better formulation:

$$
Accel=
Momentum_{short}
-
Momentum_{long}
$$

For example:

$$
Accel=R_{63}-0.5R_{126}
$$

Positive acceleration means recent performance is improving.

---

# 32. Trend acceleration

Calculate:

$$
MAAccel=
Slope_{50,t}-Slope_{50,t-20}
$$

Positive:

**trend is accelerating.**

Negative:

**trend is decelerating.**

This can detect sector deterioration before the 200-day trend breaks.

---

# 33. Relative-strength acceleration

Likewise:

$$
RSAccel=
RSR_{63}-0.5RSR_{126}
$$

This is one of my favorite factors for sector rotation.

A sector can have:

```text
6-month RS: mediocre
3-month RS: strong
1-month RS: very strong
```

That may indicate **emerging leadership**.

---

# 34. Valuation

For ETFs where fundamental data is available, calculate:

### P/E

$$
PE=\frac{Price}{EPS}
$$

### Forward P/E

$$
PE_f=\frac{Price}{ForwardEPS}
$$

### PEG

$$
PEG=\frac{PE}{EPSGrowth}
$$

### Price/book

$$
P/B=\frac{MarketCap}{BookValue}
$$

### Price/sales

$$
P/S=\frac{MarketCap}{Revenue}
$$

But **don't compare raw P/E between sectors**.

Instead calculate sector-relative valuation:

$$
ValuationZ=
\frac{PE_i-Median(PE_{sectorUniverse})}
{StdDev(PE_{sectorUniverse})}
$$

Even better, compare each sector against its **own historical valuation distribution**.

---

# 35. Valuation percentile

For ETF \(i\):

$$
PEPercentile=
PercentileRank(PE_i)
$$

Then:

$$
ValueScore=100-PEPercentile
$$

Do the same for:

* P/E
* forward P/E
* P/B
* P/S
* EV/EBITDA

Then:

$$
Value=
0.30PE+
0.30PE_f+
0.20EV/EBITDA+
0.10P/B+
0.10P/S
$$

---

# 36. Earnings growth

For sector holdings:

$$
EPSGrowth=
\frac{EPS_t}{EPS_{t-1}}-1
$$

Forward growth:

$$
ForwardEPSGrowth=
\frac{EPS_{t+1}}{EPS_t}-1
$$

Revenue growth:

$$
RevenueGrowth=
\frac{Revenue_t}{Revenue_{t-1}}-1
$$

---

# 37. Earnings revision score

This is a very powerful factor.

$$
Revision=
\frac{ForwardEPS_{current}}
{ForwardEPS_{30daysAgo}}-1
$$

Similarly:

$$
Revision_{90}=
\frac{ForwardEPS_{current}}
{ForwardEPS_{90daysAgo}}-1
$$

Positive revisions indicate analysts are becoming more optimistic.

For a forward-looking system, I would give this **more weight than trailing P/E**.

---

# 38. Final factor architecture

For your particular application, I'd use:

### Momentum — 25%

$$
M=25\%
$$

Components:

```text
21D return       5%
63D return       30%
126D return      30%
252D return      25%
Momentum accel   10%
```

### Relative strength — 15%

```text
21D RS           10%
63D RS           30%
126D RS          35%
252D RS          15%
RS acceleration  10%
```

### Trend — 15%

```text
Price vs MA20
Price vs MA50
Price vs MA200
MA alignment
MA slope
MACD
```

### Risk-adjusted performance — 15%

```text
Sharpe
Sortino
Max drawdown
Downside beta
Volatility
```

### Breadth — 10%

```text
% > MA20
% > MA50
% > MA200
A/D line
Equal-weight confirmation
```

### Valuation — 10%

```text
Forward P/E
P/E
EV/EBITDA
P/B
P/S
```

### Flows/volume — 5%

```text
Volume ratio
Dollar volume
OBV
MFI
```

### Fundamentals — 5%

```text
EPS growth
Revenue growth
EPS revisions
Margin trend
```

Total:

$$
25+15+15+15+10+10+5+5=100
$$

---

# 39. Normalize everything

This is extremely important.

**Don't add raw values together.**

Convert each factor into a cross-sectional percentile:

$$
Score_i=
100\times
\frac{Rank_i-1}{N-1}
$$

For 12 ETFs:

```text
Best ETF      = 100
2nd           = 90.9
3rd           = 81.8
...
12th          = 0
```

Alternatively use a Z-score:

$$
Z_i=\frac{x_i-\mu}{\sigma}
$$

Then transform:

$$
Score=50+10Z
$$

with clipping:

$$
Score=\min(100,\max(0,50+10Z))
$$

I prefer **percentile ranking** for your use case because it is robust to outliers.

---

# 40. Final score

The actual implementation becomes:

$$
\boxed{
SectorScore=
0.25M+
0.15RS+
0.15Trend+
0.15Risk+
0.10Breadth+
0.10Value+
0.05Flow+
0.05Fundamental
}
$$

Every component is between 0 and 100.

Therefore:

$$
0\le SectorScore\le100
$$

---

# 41. Convert score into trading categories

I'd avoid making the system overly aggressive.

|      Score | Classification      |
| ---------: | ------------------- |
| **90–100** | Strong Overweight   |
|  **80–89** | Overweight          |
|  **70–79** | Moderate Overweight |
|  **60–69** | Slight Overweight   |
|  **45–59** | Neutral             |
|  **35–44** | Slight Underweight  |
|  **25–34** | Underweight         |
|  **10–24** | Strong Underweight  |
|    **0–9** | Avoid               |

But add a **regime gate**.

For example:

```text
Bull regime:
    allow Overweight

Neutral regime:
    allow Moderate Overweight

Bear regime:
    maximum = Neutral
```

This prevents your model from blindly buying the highest-ranked sector during a market-wide risk-off event.

---

# 42. Even better: separate "score" from "signal"

This is something I'd strongly recommend for your existing quantitative application.

Don't make:

$$
Score=Signal
$$

Instead:

### Sector Score

Measures relative attractiveness:

$$
0-100
$$

### Sector Regime

```text
BULL
NEUTRAL
BEAR
```

### Sector Momentum

```text
ACCELERATING
STABLE
DECELERATING
```

### Sector Risk

```text
LOW
NORMAL
HIGH
EXTREME
```

Then your decision engine becomes:

$$
Decision=f(Score,Regime,Momentum,Risk)
$$

For example:

```text
Score = 91
Regime = BULL
Momentum = ACCELERATING
Risk = NORMAL

=> STRONG OVERWEIGHT
```

versus:

```text
Score = 91
Regime = BEAR
Momentum = DECELERATING
Risk = EXTREME

=> HOLD / NO NEW ENTRY
```

That distinction can solve a lot of the **"everything becomes Hold/Underweight"** behavior you mentioned previously.

---

# 43. My recommended production version

If I were implementing this in your quant application, I'd actually use **three layers**:

```text
                    MARKET REGIME
                         │
             ┌───────────┴───────────┐
             │                       │
         BULL/NEUTRAL              BEAR
             │                       │
             ▼                       ▼
      SECTOR FACTOR MODEL      DEFENSIVE MODEL
             │
             ▼
       12 ETF RANKING
             │
             ▼
      SCORE 0–100
             │
     ┌───────┼────────┐
     ▼       ▼        ▼
 Momentum  Quality   Risk
     │       │        │
     └───────┼────────┘
             ▼
       FINAL SCORE
             │
             ▼
     ENTRY / HOLD / EXIT
```

And I would add one more metric that is **very important for your system**:

### Expected return / risk score

Instead of merely ranking historical winners:

$$
ExpectedScore=
\frac{ExpectedReturn}{ExpectedVolatility}
$$

where expected return can combine:

$$
E[R]=
w_1 Momentum+
w_2 EarningsRevision+
w_3 Valuation+
w_4 Trend+
w_5 RelativeStrength
$$

Then:

$$
ERiskScore=
\frac{E[R]}{\sigma}
$$

That starts turning your sector ranking from a **descriptive ranking system** into a genuine **forward-looking portfolio allocation model**.

For your application, I would also **not treat SOXX as simply another sector alongside XLK**. I'd create a hierarchy:

```text
Level 1 — GICS Sector
    Technology → XLK

Level 2 — Strategic Industry
    Semiconductors → SOXX

Level 3 — Individual stocks
    NVDA
    AMD
    AVGO
    MU
    TSM
    AMAT
    LRCX
    KLAC
    MRVL
    ...
```

That gives you a much stronger **market → sector → industry → stock** ranking architecture and avoids double-counting semiconductor exposure when both XLK and SOXX rank highly.
