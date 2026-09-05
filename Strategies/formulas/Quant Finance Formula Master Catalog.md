Yes. I would make the **Quant Finance Formula Master Catalog** substantially broader than the six-pillar list above. A production quant system needs not only the headline formulas, but also the transformations, estimators, diagnostics, attribution equations, calibration equations, and execution-cost equations that connect them.

The catalog below is designed as a **master reference / implementation blueprint**. The portfolio and risk sections are consistent with standard CFA/actuarial quantitative-finance formulations, including covariance-based portfolio risk and the three major VaR approaches. ([CFA Institute][1])

---

# Quant Finance Formula Master Catalog

## Master taxonomy

| #  | Domain                                     | Approx. formula families |
| -- | ------------------------------------------ | -----------------------: |
| 1  | Market Data & Price Transformations        |                      25+ |
| 2  | Returns & Performance                      |                      30+ |
| 3  | Descriptive Statistics                     |                      30+ |
| 4  | Probability & Distributions                |                      35+ |
| 5  | Time-Series Analysis                       |                      45+ |
| 6  | Technical / Price-Action Analytics         |                      60+ |
| 7  | Volatility Modeling                        |                      40+ |
| 8  | Factor Models & Alpha                      |                      45+ |
| 9  | Cross-Sectional Quant Research             |                      35+ |
| 10 | Mean Reversion / Statistical Arbitrage     |                      35+ |
| 11 | Machine Learning Quant Metrics             |                      35+ |
| 12 | Fundamental / Equity Valuation             |                      50+ |
| 13 | Portfolio Mathematics                      |                      40+ |
| 14 | Portfolio Optimization                     |                      45+ |
| 15 | Risk Management                            |                      60+ |
| 16 | Stress / Scenario / Tail Risk              |                      35+ |
| 17 | Derivatives                                |                      80+ |
| 18 | Volatility Derivatives                     |                      30+ |
| 19 | Fixed Income                               |                      60+ |
| 20 | Credit                                     |                      40+ |
| 21 | Monte Carlo                                |                      35+ |
| 22 | Numerical Methods                          |                      40+ |
| 23 | Market Microstructure                      |                      50+ |
| 24 | Algorithmic Execution                      |                      45+ |
| 25 | Backtesting                                |                      45+ |
| 26 | Transaction Cost Analysis                  |                      30+ |
| 27 | Performance Attribution                    |                      35+ |
| 28 | Position Sizing                            |                      30+ |
| 29 | Regime Detection                           |                      30+ |
| 30 | Portfolio Monitoring / Production Controls |                      35+ |

That gives you a **500+ formula-level catalog** once the individual variants and estimators are expanded.

---

# PART I — MARKET DATA

## 1. Price transformations

### 1.1 Simple return

$$
R_t=\frac{P_t-P_{t-1}}{P_{t-1}}
$$

### 1.2 Gross return

$$
G_t=1+R_t=\frac{P_t}{P_{t-1}}
$$

### 1.3 Log return

$$
r_t=\ln\left(\frac{P_t}{P_{t-1}}\right)
$$

### 1.4 Price reconstruction

$$
P_t=P_{t-1}e^{r_t}
$$

### 1.5 Cumulative return

$$
R_{0,T}
=
\prod_{t=1}^{T}(1+R_t)-1
$$

### 1.6 Cumulative log return

$$
r_{0,T}
=
\sum_{t=1}^{T}r_t
$$

### 1.7 High-low range

$$
Range_t=H_t-L_t
$$

### 1.8 Relative range

$$
RelativeRange_t=
\frac{H_t-L_t}{C_t}
$$

### 1.9 Intraday return

$$
R_{intraday}=
\frac{C_t}{O_t}-1
$$

### 1.10 Overnight return

$$
R_{overnight}=
\frac{O_t}{C_{t-1}}-1
$$

### 1.11 Gap

$$
Gap_t=
\frac{O_t-C_{t-1}}{C_{t-1}}
$$

### 1.12 Gap percentage

$$
Gap\%=
100\frac{O_t-C_{t-1}}{C_{t-1}}
$$

### 1.13 Typical price

$$
TP_t=
\frac{H_t+L_t+C_t}{3}
$$

### 1.14 Median price

$$
MP_t=\frac{H_t+L_t}{2}
$$

### 1.15 Weighted close

$$
WC_t=
\frac{H_t+L_t+2C_t}{4}
$$

---

# PART II — RETURNS & PERFORMANCE

## 2.1 Arithmetic mean

$$
\bar R=\frac1n\sum_{i=1}^nR_i
$$

## 2.2 Geometric return

$$
R_G=
\left[
\prod_{i=1}^n(1+R_i)
\right]^{1/n}-1
$$

## 2.3 CAGR

$$
CAGR=
\left(\frac{V_T}{V_0}\right)^{1/T}-1
$$

## 2.4 Annualized arithmetic return

$$
R_{ann}\approx N\bar R
$$

## 2.5 Annualized volatility

$$
\sigma_{ann}
=
\sigma_{daily}\sqrt N
$$

## 2.6 Excess return

$$
ER=R-R_f
$$

## 2.7 Active return

$$
AR=R_p-R_b
$$

## 2.8 Tracking error

$$
TE=Std(R_p-R_b)
$$

## 2.9 Sharpe ratio

$$
SR=
\frac{E[R_p]-R_f}{\sigma_p}
$$

## 2.10 Sortino ratio

$$
Sortino=
\frac{E[R_p]-R_T}{DD}
$$

## 2.11 Information ratio

$$
IR=
\frac{E[R_p-R_b]}
{Std(R_p-R_b)}
$$

## 2.12 Treynor ratio

$$
TR=
\frac{R_p-R_f}{\beta_p}
$$

## 2.13 Calmar ratio

$$
Calmar=
\frac{CAGR}{|MDD|}
$$

## 2.14 Omega ratio

$$
\Omega(\tau)=
\frac{
\int_\tau^\infty[1-F(r)]dr
}{
\int_{-\infty}^{\tau}F(r)dr
}
$$

## 2.15 Profit factor

$$
PF=
\frac{GrossProfit}{GrossLoss}
$$

## 2.16 Expectancy

$$
E=
P(W)AvgWin-P(L)AvgLoss
$$

## 2.17 Payoff ratio

$$
PayoffRatio=
\frac{AvgWin}{AvgLoss}
$$

## 2.18 Win rate

$$
WinRate=
\frac{N_{winning}}
{N_{trades}}
$$

## 2.19 Loss rate

$$
LossRate=1-WinRate
$$

## 2.20 Break-even win rate

If payoff ratio is \(b\):

$$
p_{BE}=
\frac1{1+b}
$$

---

# PART III — RISK & DRAWDOWN PERFORMANCE

## 3.1 Running maximum

$$
M_t=\max_{s\le t}V_s
$$

## 3.2 Drawdown

$$
DD_t=
\frac{V_t-M_t}{M_t}
$$

## 3.3 Maximum drawdown

$$
MDD=\min_tDD_t
$$

## 3.4 Drawdown duration

$$
Duration=
t_{recovery}-t_{peak}
$$

## 3.5 Recovery time

Number of periods from trough until:

$$
V_t\geq V_{peak}
$$

## 3.6 Ulcer Index

$$
UI=
\sqrt{
\frac1n
\sum_{t=1}^nDD_t^2
}
$$

## 3.7 Pain index

$$
Pain=
\frac1n\sum_t|DD_t|
$$

## 3.8 Recovery factor

$$
RF=
\frac{NetProfit}{|MDD|}
$$

---

# PART IV — DESCRIPTIVE STATISTICS

## 4.1 Variance

$$
\sigma^2=
\frac1{n-1}
\sum_i(x_i-\bar x)^2
$$

## 4.2 Standard deviation

$$
\sigma=\sqrt{\sigma^2}
$$

## 4.3 Covariance

$$
Cov(X,Y)=
E[(X-\mu_X)(Y-\mu_Y)]
$$

## 4.4 Correlation

$$
\rho_{XY}=
\frac{Cov(X,Y)}
{\sigma_X\sigma_Y}
$$

## 4.5 Z-score

$$
Z=
\frac{x-\mu}{\sigma}
$$

## 4.6 Median

$$
Median=Q_{0.50}
$$

## 4.7 Quantile

$$
Q_p=F^{-1}(p)
$$

## 4.8 MAD

$$
MAD=
Median(|x_i-Median(x)|)
$$

## 4.9 Coefficient of variation

$$
CV=\frac{\sigma}{\mu}
$$

## 4.10 Skewness

$$
Skew=
\frac{E[(X-\mu)^3]}{\sigma^3}
$$

## 4.11 Kurtosis

$$
Kurt=
\frac{E[(X-\mu)^4]}{\sigma^4}
$$

## 4.12 Excess kurtosis

$$
Kurt_{excess}=Kurt-3
$$

## 4.13 Jarque-Bera

$$
JB=
\frac n6
\left[
S^2+
\frac{(K-3)^2}{4}
\right]
$$

---

# PART V — PROBABILITY

## 5.1 Expected value

$$
E[X]=\sum_xxp(x)
$$

Continuous:

$$
E[X]=\int xf(x)dx
$$

## 5.2 Variance

$$
Var(X)=E[X^2]-E[X]^2
$$

## 5.3 Conditional expectation

$$
E[X|Y]
$$

## 5.4 Conditional probability

$$
P(A|B)=
\frac{P(A\cap B)}
{P(B)}
$$

## 5.5 Bayes theorem

$$
P(A|B)=
\frac{P(B|A)P(A)}
{P(B)}
$$

## 5.6 Normal distribution

$$
f(x)=
\frac1{\sigma\sqrt{2\pi}}
e^{-\frac{(x-\mu)^2}{2\sigma^2}}
$$

## 5.7 Standardization

$$
Z=\frac{X-\mu}{\sigma}
$$

## 5.8 Lognormal expectation

If:

$$
X=e^Y,\quad Y\sim N(\mu,\sigma^2)
$$

then:

$$
E[X]=e^{\mu+\sigma^2/2}
$$

## 5.9 Poisson

$$
P(N=k)=
\frac{e^{-\lambda}\lambda^k}{k!}
$$

## 5.10 Exponential

$$
f(x)=\lambda e^{-\lambda x}
$$

## 5.11 Student-t

Useful for fat-tailed return modeling.

## 5.12 Bernoulli

$$
P(X=1)=p
$$

$$
E[X]=p
$$

$$
Var(X)=p(1-p)
$$

---

# PART VI — TIME SERIES

## 6.1 Autocorrelation

$$
\rho_k=
\frac{
\sum_t(x_t-\bar x)(x_{t-k}-\bar x)
}{
\sum_t(x_t-\bar x)^2
}
$$

## 6.2 AR(1)

$$
X_t=c+\phi X_{t-1}+\epsilon_t
$$

## 6.3 AR(p)

$$
X_t=c+\sum_{i=1}^p\phi_iX_{t-i}+\epsilon_t
$$

## 6.4 MA(q)

$$
X_t=
\mu+\epsilon_t+
\sum_{i=1}^q\theta_i\epsilon_{t-i}
$$

## 6.5 ARMA

$$
ARMA(p,q)=AR(p)+MA(q)
$$

## 6.6 Differencing

$$
\Delta X_t=X_t-X_{t-1}
$$

## 6.7 Log differencing

$$
\Delta\ln X_t
=
\ln X_t-\ln X_{t-1}
$$

## 6.8 ARIMA

$$
ARIMA(p,d,q)
$$

## 6.9 ADF

$$
\Delta y_t=
\alpha+\beta t+\gamma y_{t-1}
+\sum_i\delta_i\Delta y_{t-i}
+\epsilon_t
$$

## 6.10 Ornstein-Uhlenbeck

$$
dX_t=
\kappa(\theta-X_t)dt+\sigma dW_t
$$

## 6.11 OU half-life

$$
t_{1/2}=
\frac{\ln2}{\kappa}
$$

## 6.12 EWMA

$$
\sigma_t^2=
\lambda\sigma_{t-1}^2+
(1-\lambda)r_{t-1}^2
$$

## 6.13 GARCH(1,1)

$$
\sigma_t^2=
\omega+
\alpha\epsilon_{t-1}^2+
\beta\sigma_{t-1}^2
$$

## 6.14 GARCH persistence

$$
Persistence=\alpha+\beta
$$

## 6.15 Long-run GARCH variance

$$
\sigma_\infty^2=
\frac{\omega}{1-\alpha-\beta}
$$

---

# PART VII — TECHNICAL / PRICE ACTION

This section becomes particularly large.

## Trend

### SMA

$$
SMA_n=
\frac1n\sum_{i=0}^{n-1}P_{t-i}
$$

### EMA

$$
EMA_t=
\alpha P_t+(1-\alpha)EMA_{t-1}
$$

$$
\alpha=\frac2{n+1}
$$

### WMA

$$
WMA=
\frac{\sum_iw_iP_i}{\sum_iw_i}
$$

### Moving-average slope

$$
Slope=
\frac{MA_t-MA_{t-k}}{k}
$$

### Price/MA distance

$$
D_t=
\frac{P_t-MA_t}{MA_t}
$$

---

# Momentum

### Momentum

$$
M_n=P_t-P_{t-n}
$$

### Rate of change

$$
ROC_n=
\frac{P_t-P_{t-n}}
{P_{t-n}}
$$

### RSI

$$
RS=
\frac{AvgGain}{AvgLoss}
$$

$$
RSI=
100-\frac{100}{1+RS}
$$

### Stochastic oscillator

$$
\%K=
100
\frac{C-L_n}{H_n-L_n}
$$

### Williams %R

$$
\%R=
-100
\frac{H_n-C}{H_n-L_n}
$$

### MACD

$$
MACD=EMA_{12}-EMA_{26}
$$

### Signal

$$
Signal=EMA_9(MACD)
$$

### Histogram

$$
Hist=MACD-Signal
$$

---

# Bollinger

### Middle

$$
MB=SMA_n
$$

### Upper

$$
UB=MB+k\sigma
$$

### Lower

$$
LB=MB-k\sigma
$$

### Bandwidth

$$
BBW=
\frac{UB-LB}{MB}
$$

### %B

$$
\%B=
\frac{P-LB}{UB-LB}
$$

---

# ATR

### True range

$$
TR_t=
\max
\left[
H-L,\,
|H-C_{prev}|,\,
|L-C_{prev}|
\right]
$$

### ATR

$$
ATR_n=SMA_n(TR)
$$

### ATR percentage

$$
ATR\%=
\frac{ATR}{Price}
$$

---

# Volume

### OBV

$$
OBV_t=
OBV_{t-1}
+
sign(C_t-C_{t-1})Volume_t
$$

### Volume moving average

$$
VMA_n=SMA_n(Volume)
$$

### Relative volume

$$
RVOL=
\frac{Volume_t}
{AvgVolume_n}
$$

### Volume z-score

$$
Z_V=
\frac{V_t-\mu_V}{\sigma_V}
$$

---

# PART VIII — VOLATILITY

## 8.1 Historical volatility

$$
\sigma=
Std(r_t)\sqrt{252}
$$

## 8.2 Realized variance

$$
RV=
\sum_{i=1}^n r_i^2
$$

## 8.3 Realized volatility

$$
RVOL=\sqrt{RV}
$$

## 8.4 Parkinson

$$
\sigma_P^2=
\frac1{4n\ln2}
\sum_i
\ln^2(H_i/L_i)
$$

## 8.5 Garman-Klass

$$
\sigma_{GK}^2=
\frac1n
\sum_i
\left[
\frac12\ln^2(H_i/L_i)
-
(2\ln2-1)\ln^2(C_i/O_i)
\right]
$$

## 8.6 Rogers-Satchell

$$
RS=
\ln(H/O)\ln(H/C)
+
\ln(L/O)\ln(L/C)
$$

## 8.7 Yang-Zhang

Combines:

* overnight volatility
* Rogers-Satchell volatility
* open-close volatility

to reduce bias from opening jumps.

## 8.8 Volatility ratio

$$
VR=
\frac{\sigma_{short}}
{\sigma_{long}}
$$

## 8.9 Volatility z-score

$$
Z_\sigma=
\frac{\sigma_t-\mu_\sigma}
{\sigma_{\sigma}}
$$

## 8.10 Volatility percentile

$$
VP=
PercentileRank(\sigma_t)
$$

---

# PART IX — FACTOR MODELS & ALPHA

## 9.1 CAPM

$$
E[R_i]=R_f+
\beta_i(E[R_m]-R_f)
$$

## 9.2 Beta

$$
\beta_i=
\frac{Cov(R_i,R_m)}
{Var(R_m)}
$$

## 9.3 Alpha

$$
\alpha_i=
R_i-R_f-\beta_i(R_m-R_f)
$$

## 9.4 Market model

$$
R_i=\alpha_i+\beta_iR_m+\epsilon_i
$$

## 9.5 Fama-French

$$
R_i-R_f=
\alpha+
\beta_M(MKT)
+\beta_SSMB
+\beta_HHML
+\epsilon
$$

Extended:

$$
+\beta_RRMW+\beta_CCMA+\beta_MMOM
$$

## 9.6 Factor exposure

$$
Exposure_k=
\sum_iw_i\beta_{ik}
$$

## 9.7 Factor contribution

$$
FC_k=
Exposure_k\times FactorReturn_k
$$

## 9.8 Information coefficient

$$
IC=
Corr(PredictedReturn,ActualReturn)
$$

## 9.9 Rank IC

$$
IC_{rank}=
Spearman(prediction,return)
$$

## 9.10 ICIR

$$
ICIR=
\frac{Mean(IC)}
{Std(IC)}
$$

## 9.11 Breadth

$$
IR\approx IC\sqrt{Breadth}
$$

---

# PART X — CROSS-SECTIONAL QUANT RESEARCH

## 10.1 Cross-sectional z-score

$$
Z_{i,t}=
\frac{X_{i,t}-\mu_t}
{\sigma_t}
$$

## 10.2 Sector-neutral z-score

$$
Z_{i,t}^{sector}=
\frac{X_i-\mu_{sector}}
{\sigma_{sector}}
$$

## 10.3 Percentile rank

$$
Rank_i=
\frac{rank(X_i)-1}{N-1}
$$

## 10.4 Winsorization

$$
X_i'=
\min(\max(X_i,L),U)
$$

## 10.5 Robust z-score

$$
Z_i=
\frac{X_i-Median(X)}
{1.4826\,MAD}
$$

## 10.6 Composite factor

$$
F_i=
\sum_k w_kZ_{ik}
$$

## 10.7 Factor IC

$$
IC_k=
Corr(F_k,R_{future})
$$

## 10.8 Long-short return

$$
R_{LS}=
R_{long}-R_{short}
$$

## 10.9 Quintile spread

$$
Spread=
R_{Q5}-R_{Q1}
$$

## 10.10 Decile spread

$$
Spread=
R_{D10}-R_{D1}
$$

---

# PART XI — STATISTICAL ARBITRAGE

## 11.1 Spread

$$
S_t=P_A-\beta P_B
$$

## 11.2 Log spread

$$
S_t=
\ln P_A-\beta\ln P_B
$$

## 11.3 Hedge ratio

$$
\hat\beta=
\frac{Cov(P_A,P_B)}
{Var(P_B)}
$$

## 11.4 Spread z-score

$$
Z_t=
\frac{S_t-\mu_S}{\sigma_S}
$$

## 11.5 OU process

$$
dS_t=
\kappa(\theta-S_t)dt+
\sigma dW_t
$$

## 11.6 Half-life

$$
t_{1/2}=\frac{\ln2}{\kappa}
$$

## 11.7 Cointegration

$$
Y_t=\alpha+\beta X_t+\epsilon_t
$$

and require:

$$
\epsilon_t\sim I(0)
$$

## 11.8 Hurst exponent

One common rescaled-range approximation:

$$
E[R/S]\sim cT^H
$$

Interpretation:

$$
H<0.5
$$

often associated with anti-persistence;

$$
H>0.5
$$

with persistence.

---

# PART XII — MACHINE LEARNING

## 12.1 MSE

$$
MSE=
\frac1n
\sum_i(y_i-\hat y_i)^2
$$

## 12.2 RMSE

$$
RMSE=\sqrt{MSE}
$$

## 12.3 MAE

$$
MAE=
\frac1n\sum_i|y_i-\hat y_i|
$$

## 12.4 \(R^2\)

$$
R^2=
1-\frac{SS_{res}}{SS_{tot}}
$$

## 12.5 Classification accuracy

$$
Accuracy=
\frac{TP+TN}
{TP+TN+FP+FN}
$$

## 12.6 Precision

$$
Precision=
\frac{TP}{TP+FP}
$$

## 12.7 Recall

$$
Recall=
\frac{TP}{TP+FN}
$$

## 12.8 F1

$$
F1=
2\frac{Precision\cdot Recall}
{Precision+Recall}
$$

## 12.9 Log loss

$$
-\frac1n
\sum_i
[y_i\ln p_i+(1-y_i)\ln(1-p_i)]
$$

## 12.10 Brier score

$$
Brier=
\frac1n
\sum_i(p_i-y_i)^2
$$

## 12.11 Feature importance

Can use:

* permutation importance
* SHAP
* gain
* split count

## 12.12 Regularized regression

Ridge:

$$
\min_\beta
||y-X\beta||^2+\lambda||\beta||_2^2
$$

Lasso:

$$
\min_\beta
||y-X\beta||^2+\lambda||\beta||_1
$$

---

# PART XIII — FUNDAMENTAL / EQUITY VALUATION

This is an important addition to your stock research system.

## Earnings

$$
EPS=
\frac{NetIncome-PreferredDividends}
{WeightedAvgShares}
$$

## P/E

$$
PE=\frac{Price}{EPS}
$$

## Earnings yield

$$
EY=\frac{EPS}{Price}
$$

## Forward P/E

$$
ForwardPE=
\frac{Price}{ForwardEPS}
$$

## PEG

$$
PEG=
\frac{PE}{EPSGrowth}
$$

## Price/Sales

$$
P/S=
\frac{MarketCap}{Revenue}
$$

## Price/Book

$$
P/B=
\frac{MarketCap}{BookValue}
$$

## EV

$$
EV=
MarketCap+Debt+Preferred+MinorityInterest-Cash
$$

## EV/EBITDA

$$
EV/EBITDA=
\frac{EV}{EBITDA}
$$

## FCF

$$
FCF=OperatingCashFlow-CapEx
$$

## FCF yield

$$
FCFYield=
\frac{FCF}{MarketCap}
$$

## ROE

$$
ROE=
\frac{NetIncome}{AverageEquity}
$$

## ROA

$$
ROA=
\frac{NetIncome}{AverageAssets}
$$

## ROIC

$$
ROIC=
\frac{NOPAT}{InvestedCapital}
$$

## Gross margin

$$
GM=
\frac{Revenue-COGS}{Revenue}
$$

## Operating margin

$$
OM=
\frac{OperatingIncome}{Revenue}
$$

## Net margin

$$
NM=
\frac{NetIncome}{Revenue}
$$

## Revenue growth

$$
g_R=
\frac{Revenue_t-Revenue_{t-1}}
{Revenue_{t-1}}
$$

## EPS growth

$$
g_{EPS}=
\frac{EPS_t-EPS_{t-1}}
{EPS_{t-1}}
$$

---

# PART XIV — DCF

## 14.1 Present value

$$
PV=
\frac{CF_t}{(1+r)^t}
$$

## 14.2 DCF

$$
EV=
\sum_{t=1}^T
\frac{FCF_t}{(1+WACC)^t}
+
\frac{TV}{(1+WACC)^T}
$$

## 14.3 Terminal value

$$
TV=
\frac{FCF_{T+1}}
{WACC-g}
$$

## 14.4 Equity value

$$
EquityValue=
EV-Debt+Cash
$$

## 14.5 Fair value per share

$$
FV=
\frac{EquityValue}
{SharesOutstanding}
$$

## 14.6 WACC

$$
WACC=
\frac{E}{D+E}R_e+
\frac{D}{D+E}R_d(1-T)
$$

## 14.7 Cost of equity

$$
R_e=
R_f+\beta(E[R_m]-R_f)
$$

---

# PART XV — PORTFOLIO MATHEMATICS

Portfolio expected return:

$$
E[R_p]=w^T\mu
$$

Portfolio variance:

$$
\sigma_p^2=w^T\Sigma w
$$

Portfolio volatility:

$$
\sigma_p=\sqrt{w^T\Sigma w}
$$

Two-asset form:

$$
\sigma_p^2=
w_1^2\sigma_1^2+
w_2^2\sigma_2^2+
2w_1w_2\rho_{12}\sigma_1\sigma_2
$$

These are fundamental portfolio relationships also emphasized in current CFA material. ([CFA Institute][1])

---

# PART XVI — PORTFOLIO OPTIMIZATION

## 16.1 Markowitz

$$
\max_w
w^T\mu-\frac{\lambda}{2}w^T\Sigma w
$$

subject to:

$$
1^Tw=1
$$

## 16.2 Minimum variance

$$
\min_w w^T\Sigma w
$$

## 16.3 Global minimum variance

$$
w_{GMV}=
\frac{\Sigma^{-1}1}
{1^T\Sigma^{-1}1}
$$

## 16.4 Tangency portfolio

$$
w_T\propto
\Sigma^{-1}(\mu-r_f1)
$$

## 16.5 Sharpe optimization

$$
\max_w
\frac{w^T(\mu-r_f1)}
{\sqrt{w^T\Sigma w}}
$$

## 16.6 Risk parity

$$
RC_i=
\frac{w_i(\Sigma w)_i}
{\sigma_p}
$$

Target:

$$
RC_i=\frac{\sigma_p}{N}
$$

## 16.7 Inverse volatility

$$
w_i=
\frac{1/\sigma_i}
{\sum_j1/\sigma_j}
$$

## 16.8 Volatility targeting

$$
Leverage=
\frac{\sigma_{target}}
{\sigma_{forecast}}
$$

## 16.9 Turnover

$$
Turnover=
\frac12\sum_i|w_i-w_i^{old}|
$$

## 16.10 Concentration

$$
HHI=\sum_iw_i^2
$$

## 16.11 Effective number of holdings

$$
N_{eff}=
\frac1{\sum_iw_i^2}
$$

---

# PART XVII — COVARIANCE MODELING

## Sample covariance

$$
S=
\frac1{T-1}
X^TX
$$

## Correlation matrix

$$
C_{ij}=
\frac{\Sigma_{ij}}
{\sigma_i\sigma_j}
$$

## EWMA covariance

$$
\Sigma_t=
\lambda\Sigma_{t-1}
+
(1-\lambda)r_{t-1}r_{t-1}^T
$$

## Shrinkage

$$
\hat\Sigma=
\lambda F+(1-\lambda)S
$$

## PCA

$$
\Sigma v_i=\lambda_iv_i
$$

## Explained variance

$$
EV_i=
\frac{\lambda_i}
{\sum_j\lambda_j}
$$

---

# PART XVIII — BLACK-LITTERMAN

Equilibrium return:

$$
\Pi=\delta\Sigma w_{mkt}
$$

Posterior:

$$
\mu_{BL}
=
[
(\tau\Sigma)^{-1}
+
P^T\Omega^{-1}P
]^{-1}
[
(\tau\Sigma)^{-1}\Pi+
P^T\Omega^{-1}q
]
$$

This is particularly useful when your alpha model produces **views with different confidence levels**, rather than pretending all forecasts are equally reliable.

---

# PART XIX — RISK

## 19.1 VaR

$$
P(L>VaR_\alpha)=1-\alpha
$$

## 19.2 Parametric VaR

$$
VaR_\alpha=
z_\alpha\sigma_pV
$$

## 19.3 Historical VaR

$$
VaR_\alpha=
Quantile_\alpha(L)
$$

## 19.4 Monte Carlo VaR

$$
VaR_\alpha=
Quantile_\alpha(L^{sim})
$$

These three methods are the standard major VaR approaches identified by CFA risk-management material. ([CFA Institute][2])

## 19.5 Expected Shortfall

$$
ES_\alpha=
E[L|L>VaR_\alpha]
$$

## 19.6 CVaR

$$
CVaR_\alpha=
E[L|L>VaR_\alpha]
$$

## 19.7 Marginal VaR

$$
MVaR_i=
\frac{\partial VaR}{\partial w_i}
$$

## 19.8 Component VaR

$$
CVaR_i=
w_iMVaR_i
$$

## 19.9 Incremental VaR

$$
IVaR_i=
VaR(P+\Delta P_i)-VaR(P)
$$

---

# PART XX — TAIL RISK

## 20.1 Downside deviation

$$
DD=
\sqrt{
\frac1n
\sum_i
\min(R_i-R_T,0)^2
}
$$

## 20.2 Semi-variance

$$
SemiVar=
E[
\min(R-\mu,0)^2
]
$$

## 20.3 Tail ratio

$$
TailRatio=
\frac{Q_{0.95}}
{|Q_{0.05}|}
$$

## 20.4 EVT exceedance

$$
Y=X-u
$$

## 20.5 GPD

$$
G(y)=
1-
\left(
1+\frac{\xi y}{\beta}
\right)^{-1/\xi}
$$

## 20.6 Maximum loss

$$
MaxLoss=\min_tR_t
$$

---

# PART XXI — STRESS TESTING

Scenario portfolio P&L:

$$
\Delta P
\approx
\sum_i
\Delta_i\Delta S_i
+
\frac12
\Gamma_i(\Delta S_i)^2
$$

Add volatility:

$$
+
Vega_i\Delta\sigma_i
$$

Rates:

$$
+\rho_i\Delta r_i
$$

Cross terms can be added for more sophisticated scenario engines.

---

# PART XXII — DERIVATIVES

## Forward

$$
F_0=S_0e^{rT}
$$

With dividend yield:

$$
F_0=S_0e^{(r-q)T}
$$

## Forward payoff — long

$$
Payoff_T=S_T-K
$$

## Forward payoff — short

$$
Payoff_T=K-S_T
$$

## Call payoff

$$
C_T=\max(S_T-K,0)
$$

## Put payoff

$$
P_T=\max(K-S_T,0)
$$

## Put-call parity

$$
C-P=S_0e^{-qT}-Ke^{-rT}
$$

---

# PART XXIII — BLACK-SCHOLES

$$
C=S_0e^{-qT}N(d_1)
-
Ke^{-rT}N(d_2)
$$

$$
P=
Ke^{-rT}N(-d_2)
-
S_0e^{-qT}N(-d_1)
$$

$$
d_1=
\frac{
\ln(S_0/K)
+
(r-q+\sigma^2/2)T
}
{\sigma\sqrt T}
$$

$$
d_2=d_1-\sigma\sqrt T
$$

---

# PART XXIV — OPTION GREEKS

## Delta

$$
\Delta_C=e^{-qT}N(d_1)
$$

$$
\Delta_P=e^{-qT}[N(d_1)-1]
$$

## Gamma

$$
\Gamma=
\frac{
e^{-qT}\phi(d_1)
}
{S\sigma\sqrt T}
$$

## Vega

$$
Vega=
Se^{-qT}\phi(d_1)\sqrt T
$$

## Theta

Call:

$$
\Theta_C=
-\frac{Se^{-qT}\phi(d_1)\sigma}
{2\sqrt T}
-rKe^{-rT}N(d_2)
+
qSe^{-qT}N(d_1)
$$

## Rho

$$
\rho_C=
KTe^{-rT}N(d_2)
$$

---

# PART XXV — HIGHER-ORDER GREEKS

## Vanna

$$
Vanna=
\frac{\partial^2V}
{\partial S\partial\sigma}
$$

## Volga / Vomma

$$
Volga=
\frac{\partial Vega}{\partial\sigma}
$$

For Black-Scholes:

$$
Volga=
Vega
\frac{d_1d_2}{\sigma}
$$

## Charm

$$
Charm=
-\frac{\partial\Delta}{\partial t}
$$

## Speed

$$
Speed=
\frac{\partial\Gamma}{\partial S}
$$

## Color

$$
Color=
\frac{\partial\Gamma}{\partial t}
$$

These higher-order Greeks matter particularly when a portfolio has substantial nonlinear option exposure. A current open-source quant library, for example, explicitly includes vanna and volga alongside vanilla Greeks. ([GitHub][3])

---

# PART XXVI — IMPLIED VOLATILITY

Solve:

$$
C_{BS}(\sigma_{imp})=C_{market}
$$

Newton iteration:

$$
\sigma_{n+1}
=
\sigma_n-
\frac{
C(\sigma_n)-C_{market}
}{
Vega(\sigma_n)
}
$$

Bisection is preferable when numerical robustness is more important than speed.

---

# PART XXVII — VOLATILITY SURFACE

For strike \(K\) and maturity \(T\):

$$
\sigma_{imp}=\sigma(K,T)
$$

Moneyness:

$$
m=\ln(K/F)
$$

Delta-based smile:

$$
\sigma=\sigma(\Delta,T)
$$

Term structure:

$$
\sigma=\sigma(T)
$$

Volatility skew:

$$
Skew=
\frac{\partial\sigma_{imp}}
{\partial K}
$$

Volatility curvature:

$$
Curvature=
\frac{\partial^2\sigma_{imp}}
{\partial K^2}
$$

---

# PART XXVIII — HESTON

$$
dS_t=rS_tdt+\sqrt{v_t}S_tdW_t^S
$$

$$
dv_t=
\kappa(\theta-v_t)dt+
\xi\sqrt{v_t}dW_t^v
$$

$$
dW_t^SdW_t^v=\rho dt
$$

Feller:

$$
2\kappa\theta\geq\xi^2
$$

---

# PART XXIX — SABR

$$
dF_t=\alpha_tF_t^\beta dW_1
$$

$$
d\alpha_t=\nu\alpha_tdW_2
$$

$$
dW_1dW_2=\rho dt
$$

Parameters:

$$
(\alpha,\beta,\rho,\nu)
$$

---

# PART XXX — LOCAL VOLATILITY

Dupire:

$$
\sigma_{loc}^2(K,T)
=
\frac{
\partial_TC+
(r-q)K\partial_KC+
qC
}{
\frac12K^2\partial_{KK}C
}
$$

---

# PART XXXI — STOCHASTIC CALCULUS

## Brownian

$$
dW^2=dt
$$

$$
dt\,dW=0
$$

$$
dt^2=0
$$

## General SDE

$$
dX_t=
\mu(X,t)dt+
\sigma(X,t)dW_t
$$

## Itô

$$
df=
f_tdt+
f_xdX+
\frac12f_{xx}(dX)^2
$$

## Risk-neutral transformation

$$
dS=
rSdt+\sigma SdW^Q
$$

## Fundamental pricing equation

$$
V_t=
E_t^Q
\left[
e^{-\int_t^Tr_sds}
V_T
\right]
$$

---

# PART XXXII — FIXED INCOME

## Bond price

$$
P=
\sum_{t=1}^T
\frac{CF_t}{(1+y)^t}
$$

## Zero-coupon

$$
P=e^{-yT}
$$

## Yield

$$
y=
-\frac{\ln P}{T}
$$

## Forward rate

$$
f(T_1,T_2)=
\frac{
\ln P(0,T_1)-\ln P(0,T_2)
}
{T_2-T_1}
$$

## Macaulay duration

$$
D_M=
\frac{\sum_ttPV(CF_t)}
{P}
$$

## Modified duration

$$
D_{mod}=
\frac{D_M}{1+y/m}
$$

## Price sensitivity

$$
\frac{\Delta P}{P}
\approx
-D_{mod}\Delta y
$$

## Convexity

$$
Conv=
\frac1P
\frac{\partial^2P}{\partial y^2}
$$

## Duration-convexity approximation

$$
\frac{\Delta P}{P}
\approx
-D\Delta y+
\frac12Conv(\Delta y)^2
$$

---

# PART XXXIII — SHORT-RATE MODELS

## Vasicek

$$
dr=
\kappa(\theta-r)dt+
\sigma dW
$$

## CIR

$$
dr=
\kappa(\theta-r)dt+
\sigma\sqrt r\,dW
$$

## Hull-White

$$
dr=
[\theta(t)-ar]dt+\sigma dW
$$

## Bond price

$$
P(t,T)=A(t,T)e^{-B(t,T)r_t}
$$

---

# PART XXXIV — CREDIT

## Expected loss

$$
EL=PD\times LGD\times EAD
$$

## LGD

$$
LGD=1-Recovery
$$

## Hazard rate

$$
\lambda(t)=
\frac{f(t)}{S(t)}
$$

## Survival probability

$$
S(t)=
e^{-\int_0^t\lambda(u)du}
$$

## Default probability

$$
PD(0,T)=1-S(T)
$$

## Approximate credit spread

$$
Spread\approx PD\times LGD
$$

---

# PART XXXV — XVA

$$
XVA=
CVA+DVA+FVA+KVA+MVA+\cdots
$$

CVA:

$$
CVA=
(1-R)
\int_0^T
DF(t)EPE(t)dPD(t)
$$

Expected positive exposure:

$$
EPE(t)=E[\max(V_t,0)]
$$

---

# PART XXXVI — MONTE CARLO

## Basic estimator

$$
\hat\mu=
\frac1N\sum_{i=1}^Nf(X_i)
$$

## Standard error

$$
SE=
\frac{s}{\sqrt N}
$$

## Confidence interval

$$
\hat\mu\pm z_{\alpha/2}SE
$$

## GBM simulation

$$
S_{t+\Delta t}
=
S_t
e^{
(\mu-\sigma^2/2)\Delta t+
\sigma\sqrt{\Delta t}Z
}
$$

## Euler-Maruyama

$$
X_{t+\Delta t}
=
X_t+
a\Delta t+
b\sqrt{\Delta t}Z
$$

## Antithetic variates

Use:

$$
Z
$$

and:

$$
-Z
$$

## Control variate

$$
X^*=X-\beta(Y-E[Y])
$$

Optimal:

$$
\beta^*=
\frac{Cov(X,Y)}
{Var(Y)}
$$

## Importance sampling

$$
E_p[f(X)]
=
E_q
\left[
f(X)\frac{p(X)}{q(X)}
\right]
$$

---

# PART XXXVII — NUMERICAL METHODS

## Newton-Raphson

$$
x_{n+1}
=
x_n-\frac{f(x_n)}{f'(x_n)}
$$

## Secant

$$
x_{n+1}
=
x_n-
f(x_n)
\frac{x_n-x_{n-1}}
{f(x_n)-f(x_{n-1})}
$$

## Bisection

$$
x_m=\frac{a+b}{2}
$$

## Central derivative

$$
f'(x)\approx
\frac{f(x+h)-f(x-h)}
{2h}
$$

## Second derivative

$$
f''(x)\approx
\frac{f(x+h)-2f(x)+f(x-h)}
{h^2}
$$

---

# PART XXXVIII — FINITE DIFFERENCE

Black-Scholes PDE:

$$
V_t+
rSV_S+
\frac12\sigma^2S^2V_{SS}
-rV=0
$$

First derivative:

$$
V_S\approx
\frac{V_{i+1}-V_{i-1}}
{2\Delta S}
$$

Second:

$$
V_{SS}\approx
\frac{V_{i+1}-2V_i+V_{i-1}}
{\Delta S^2}
$$

Crank-Nicolson:

$$
V^n=
V^{n+1}
+
\frac{\Delta t}{2}
[
LV^n+LV^{n+1}
]
$$

---

# PART XXXIX — CHOLESKY / CORRELATION

If:

$$
\Sigma=LL^T
$$

then:

$$
X=LZ
$$

where:

$$
Z\sim N(0,I)
$$

and therefore:

$$
Cov(X)=\Sigma
$$

This is extremely useful for Monte Carlo portfolio simulations.

---

# PART XL — MARKET MICROSTRUCTURE

## Bid-ask spread

$$
Spread=Ask-Bid
$$

## Relative spread

$$
Spread\%=
\frac{Ask-Bid}{Mid}
$$

## Midpoint

$$
Mid=\frac{Bid+Ask}{2}
$$

## Order imbalance

$$
OBI=
\frac{BidSize-AskSize}
{BidSize+AskSize}
$$

## Microprice

$$
Microprice=
\frac{
Ask(BidSize)+Bid(AskSize)
}{
BidSize+AskSize
}
$$

## Depth

$$
Depth_k=
\sum_{i=1}^kSize_i
$$

## Kyle lambda

$$
\Delta P=\lambda Q
$$

## Amihud

$$
ILLIQ=
\frac{|R|}
{DollarVolume}
$$

## Turnover

$$
Turnover=
\frac{Volume}
{SharesOutstanding}
$$

---

# PART XLI — EXECUTION

## VWAP

$$
VWAP=
\frac{\sum_iP_iV_i}
{\sum_iV_i}
$$

## TWAP

$$
TWAP=
\frac1N\sum_iP_i
$$

## POV

$$
POV=
\frac{TraderVolume}
{MarketVolume}
$$

## Participation constraint

$$
\frac{Q_t}{Volume_t}
\leq POV_{max}
$$

## Slippage

$$
Slippage=
P_{execution}-P_{benchmark}
$$

## Implementation shortfall

$$
IS=
Q(P_{execution}-P_{arrival})
$$

## Market impact

A common empirical structure:

$$
Impact\propto
\sigma
\sqrt{\frac{Q}{V}}
$$

## Execution cost

$$
Cost=
Commission+
Spread+
Impact+
Slippage
$$

---

# PART XLII — ALMGREN-CHRISS

Inventory:

$$
x(0)=X
$$

$$
x(T)=0
$$

Execution rate:

$$
v(t)=-\frac{dx}{dt}
$$

Temporary impact:

$$
g(v)=\eta v
$$

Permanent impact:

$$
h(v)=\gamma v
$$

Objective:

$$
\min
E[Cost]
+
\lambda Var(Cost)
$$

This creates the fundamental execution trade-off:

$$
\boxed{
Market\ Impact
\leftrightarrow
Execution\ Risk
}
$$

---

# PART XLIII — ORDER FLOW

## Signed volume

$$
SV_t=q_tV_t
$$

where:

$$
q_t\in\{-1,+1\}
$$

## Volume imbalance

$$
VI=
\frac{V_{buy}-V_{sell}}
{V_{buy}+V_{sell}}
$$

## Order-flow imbalance

$$
OFI=
\Delta BidDepth-\Delta AskDepth
$$

## Trade intensity

$$
Intensity=
\frac{Trades}{Time}
$$

## Poisson arrivals

$$
P(N(t)=k)=
\frac{(\lambda t)^ke^{-\lambda t}}
{k!}
$$

## Hawkes intensity

$$
\lambda_t=
\mu+
\sum_{t_i<t}
\alpha e^{-\beta(t-t_i)}
$$

---

# PART XLIV — BACKTESTING

## Trade return

$$
R_{trade}=
\frac{P_{exit}-P_{entry}}
{P_{entry}}
$$

## Long P&L

$$
PnL=Q(P_{exit}-P_{entry})
$$

## Short P&L

$$
PnL=Q(P_{entry}-P_{exit})
$$

## Net P&L

$$
NetPnL=
GrossPnL-
TransactionCosts
$$

## Turnover

$$
TO=
\frac12
\sum_i|w_{i,t}-w_{i,t-1}|
$$

## Capacity

$$
Capacity
\propto
ADV\times ParticipationRate
$$

## MAE

$$
MAE=
\min_t
\frac{P_t-P_{entry}}
{P_{entry}}
$$

## MFE

$$
MFE=
\max_t
\frac{P_t-P_{entry}}
{P_{entry}}
$$

## Profit factor

$$
PF=
\frac{GrossProfit}{GrossLoss}
$$

---

# PART XLV — TRANSACTION COST ANALYSIS

Total cost:

$$
TCA=
Commission+
SpreadCost+
MarketImpact+
Slippage+
OpportunityCost
$$

## Effective spread

$$
EffectiveSpread=
2|P_{trade}-Mid|
$$

## Realized spread

$$
RealizedSpread=
2q(P_{trade}-Mid_{future})
$$

## Price impact

$$
PI=
2q(Mid_{future}-Mid_{trade})
$$

## Opportunity cost

$$
OC=
Q_{unfilled}(P_{future}-P_{decision})
$$

---

# PART XLVI — PERFORMANCE ATTRIBUTION

## Total portfolio return

$$
R_p=\sum_iw_iR_i
$$

## Allocation effect

Conceptually:

$$
Allocation_i=
(w_{p,i}-w_{b,i})
(R_{b,i}-R_b)
$$

## Selection effect

$$
Selection_i=
w_{b,i}(R_{p,i}-R_{b,i})
$$

## Interaction

$$
Interaction_i=
(w_{p,i}-w_{b,i})
(R_{p,i}-R_{b,i})
$$

## Active contribution

$$
ActiveContribution_i=
w_{p,i}R_{p,i}-w_{b,i}R_{b,i}
$$

---

# PART XLVII — POSITION SIZING

## Fixed fractional

$$
Position=
Capital\times RiskFraction
$$

## Volatility sizing

$$
Position=
\frac{Capital\times RiskBudget}
{\sigma}
$$

## Stop-loss sizing

$$
PositionSize=
\frac{RiskCapital}
{|Entry-Stop|}
$$

## ATR sizing

$$
StopDistance=kATR
$$

$$
Position=
\frac{RiskCapital}
{kATR}
$$

## Kelly

$$
f^*=
\frac{bp-q}{b}
$$

## Continuous Kelly

$$
f^*=
\frac{\mu-r_f}{\sigma^2}
$$

## Fractional Kelly

$$
f_{actual}=kf^*
$$

where:

$$
0<k<1
$$

---

# PART XLVIII — REGIME DETECTION

## Volatility regime

$$
Regime_t=
I(\sigma_t>\sigma_{threshold})
$$

## Trend regime

$$
Trend=
sign(MA_{short}-MA_{long})
$$

## HMM transition probability

$$
P(S_t=j|S_{t-1}=i)
$$

## HMM emission

$$
P(X_t|S_t)
$$

## Regime posterior

$$
P(S_t|X_{1:t})
$$

## Markov transition matrix

$$
P=
\begin{bmatrix}
p_{11}&p_{12}\\
p_{21}&p_{22}
\end{bmatrix}
$$

with:

$$
\sum_jp_{ij}=1
$$

---

# PART XLIX — KALMAN FILTER

State:

$$
x_t=Ax_{t-1}+w_t
$$

Observation:

$$
y_t=Cx_t+v_t
$$

Prediction:

$$
\hat x_{t|t-1}
=A\hat x_{t-1|t-1}
$$

Prediction covariance:

$$
P_{t|t-1}
=
AP_{t-1}A^T+Q
$$

Kalman gain:

$$
K_t=
P_{t|t-1}C^T
(CP_{t|t-1}C^T+R)^{-1}
$$

Update:

$$
\hat x_t=
\hat x_{t|t-1}
+
K_t(y_t-C\hat x_{t|t-1})
$$

---

# PART L — PRODUCTION QUANT METRICS

These are not always found in traditional textbooks, but they are extremely important if this catalog is intended to become the mathematics behind a **real trading application**.

## Signal decay

$$
Decay(k)=
Corr(Signal_t,R_{t+k})
$$

## Alpha half-life

Find \(k\) where:

$$
Decay(k)=\frac12Decay(0)
$$

## Signal turnover

$$
Turnover_{signal}
=
\sum_i|Signal_{i,t}-Signal_{i,t-1}|
$$

## Forecast error

$$
FE_t=R_t-\hat R_t
$$

## Forecast bias

$$
Bias=
E[\hat R-R]
$$

## Calibration error

For predicted probabilities:

$$
CalibrationError=
|P_{pred}-P_{observed}|
$$

## Signal IC decay

$$
IC(k)=
Corr(S_t,R_{t+k})
$$

## Alpha capacity

$$
Capacity\approx
\frac{ExpectedAlpha}
{MarginalTradingCost}
$$

---

# PART LI — A QUANT STOCK-SCORING ENGINE

For your particular stock-analysis application, this is where I would combine the catalog.

Suppose you calculate:

### Value

$$
ValueScore=
w_1Z(EarningsYield)
+w_2Z(FCFYield)
-w_3Z(EV/EBITDA)
$$

### Quality

$$
QualityScore=
w_1Z(ROIC)
+w_2Z(ROE)
+w_3Z(Margin)
-w_4Z(Leverage)
$$

### Growth

$$
GrowthScore=
w_1Z(RevenueGrowth)
+w_2Z(EPSGrowth)
+w_3Z(FCFGrowth)
$$

### Momentum

$$
MomentumScore=
w_1Z(Momentum_{3m})
+w_2Z(Momentum_{6m})
+w_3Z(Momentum_{12m})
$$

### Risk

$$
RiskScore=
-w_1Z(Volatility)
-w_2Z(MDD)
-w_3Z(Beta)
-w_4Z(ES)
$$

### Liquidity

$$
LiquidityScore=
-w_1Z(Spread)
-w_2Z(ILLIQ)
+w_3Z(ADV)
$$

Then:

$$
\boxed{
CompositeScore=
\sum_k w_kFactorScore_k
}
$$

---

# PART LII — ALPHA → POSITION → EXECUTION

This is arguably the most important mathematical chain for your application.

## Step 1 — Expected return

$$
\hat R_i
=
E[R_{i,t+1}|X_t]
$$

## Step 2 — Expected alpha

$$
\hat\alpha_i=
\hat R_i-
R_{benchmark,i}
$$

## Step 3 — Risk-adjusted alpha

$$
RA_i=
\frac{\hat\alpha_i}{\hat\sigma_i}
$$

## Step 4 — Portfolio risk

$$
\sigma_p=
\sqrt{w^T\Sigma w}
$$

## Step 5 — Position size

$$
w_i=f(\hat\alpha_i,\sigma_i,\Sigma,
RiskBudget)
$$

## Step 6 — Liquidity constraint

$$
Q_i\leq ADV_i\times POV_{max}
$$

## Step 7 — Execution cost

$$
TC_i=
Spread_i+
Impact_i+
Commission_i
$$

## Step 8 — Net expected alpha

$$
NetAlpha_i=
GrossAlpha_i-TC_i
$$

## Step 9 — Trade only if

$$
\boxed{
NetAlpha_i>MinimumEconomicThreshold
}
$$

This last step is **very important**.

A stock can have a statistically attractive alpha but still be economically untradable after:

$$
Spread+
Slippage+
Impact+
Turnover+
Risk
$$

---

# PART LIII — THE MASTER DECISION EQUATION

For a sophisticated equity quant engine, I would ultimately think in terms of:

$$
\boxed{
ExpectedNetReturn
=
ExpectedAlpha
-
TransactionCost
-
RiskPenalty
}
$$

or:

$$
\boxed{
Score_i=
\frac{
E[R_i]-R_{benchmark}-TC_i
}{
Risk_i
}
}
$$

Then portfolio construction solves:

$$
\boxed{
\max_w
\left[
w^T\hat\alpha
-
TC(w)
-
\lambda Risk(w)
\right]
}
$$

subject to:

$$
\sum_iw_i=1
$$

$$
w_i^{min}\leq w_i\leq w_i^{max}
$$

$$
GrossExposure\leq G_{max}
$$

$$
NetExposure\leq N_{max}
$$

$$
SectorExposure\leq S_{max}
$$

$$
FactorExposure\leq F_{max}
$$

$$
Turnover\leq T_{max}
$$

$$
LiquidityRisk\leq L_{max}
$$

Then execution solves:

$$
\boxed{
\min_{execution}
ExpectedCost+
\lambda_{exec}ExecutionRisk
}
$$

This is the mathematical bridge from **quant research to an actual trading system**.

---

# The hierarchy I recommend for your application

Rather than implementing these 500+ calculations as one enormous indicator library, I would divide your system into **nine calculation engines**:

```text
                    QUANT ENGINE
                         │
        ┌────────────────┼────────────────┐
        │                │                │
        ▼                ▼                ▼
   DATA ENGINE       FEATURE ENGINE    FUNDAMENTAL
        │                │                │
        │                ▼                │
        │          ALPHA ENGINE            │
        │                │                │
        └────────────────┼────────────────┘
                         ▼
                    RISK ENGINE
                         │
                         ▼
                 PORTFOLIO ENGINE
                         │
                         ▼
                  POSITION ENGINE
                         │
                         ▼
                 EXECUTION ENGINE
                         │
                         ▼
                    TCA ENGINE
                         │
                         ▼
                  FEEDBACK ENGINE
```

### Data Engine

Returns, OHLCV, corporate actions, normalization, missing data.

### Feature Engine

Technical, volatility, statistical, factor, fundamental and microstructure features.

### Alpha Engine

Forecast:

$$
E[R_{t+1}|X_t]
$$

and measure:

$$
IC,\ ICIR,\ Alpha,\ HitRate,\ Decay
$$

### Risk Engine

$$
\sigma,\beta,VaR,ES,MDD,Stress,Exposure
$$

### Portfolio Engine

$$
w^T\mu,\quad
w^T\Sigma w,\quad
RC_i,\quad
Turnover
$$

### Position Engine

Converts portfolio targets into actual shares/contracts.

### Execution Engine

$$
VWAP,\ TWAP,\ POV,\ IS,\ Almgren-Chriss
$$

### TCA Engine

Measures whether your theoretical alpha survived:

$$
Spread+Impact+Slippage+Commission
$$

### Feedback Engine

Compares:

$$
PredictedReturn
$$

against:

$$
ActualReturn
$$

and:

$$
ExpectedCost
$$

against:

$$
ActualCost
$$

and feeds the results back into model calibration.

---

## One particularly important addition to your existing quant system

Given your earlier observation that your system has been producing **mostly Hold/Underweight signals even when stocks have moved substantially**, I would add a distinct layer for:

$$
\boxed{\text{Alpha Opportunity Detection}}
$$

rather than relying solely on absolute valuation scores.

It should calculate:

$$
Opportunity=
ExpectedReturn-
ExpectedReturn_{consensus}
$$

$$
ValueGap=
FairValue-Price
$$

$$
MomentumConfirmation=
f(Momentum,Volume,Trend)
$$

$$
RegimeAdjustment=
f(Volatility,MarketRegime)
$$

$$
LiquidityAdjustment=
f(Spread,ADV,Impact)
$$

and ultimately:

$$
\boxed{
TradeScore=
\frac{
ExpectedAlpha
-
ExpectedTransactionCost
}{
ExpectedRisk
}
}
$$

This helps distinguish **"the stock is not attractive in absolute terms"** from **"the stock is attractive relative to its opportunity set and current market regime."**

That distinction becomes particularly important once faster competing systems are continuously arbitraging away obvious value opportunities.

---

### Recommended implementation priority

If you want to turn this catalog into an actual software specification, I would implement it in this order:

**Phase 1 — Research**

1. Returns
2. Volatility
3. Correlation/covariance
4. Technical features
5. Fundamental factors
6. Factor models
7. Alpha scores
8. IC/ICIR
9. Regime detection

**Phase 2 — Portfolio**

10. Portfolio risk
11. Factor exposure
12. Risk contribution
13. Position sizing
14. Optimization
15. Turnover constraints
16. Transaction-cost modeling

**Phase 3 — Risk**

17. VaR
18. Expected Shortfall
19. Stress testing
20. Drawdown
21. Liquidity risk
22. Concentration risk
23. Tail risk

**Phase 4 — Execution**

24. Spread
25. Microprice
26. Order imbalance
27. VWAP
28. TWAP
29. POV
30. Implementation shortfall
31. Market impact
32. Almgren-Chriss
33. TCA

**Phase 5 — Feedback**

34. Fill quality
35. Slippage attribution
36. Alpha decay
37. Forecast calibration
38. realized-vs-predicted risk
39. realized-vs-predicted transaction cost
40. model degradation detection

This produces a much more complete **research → signal → portfolio → execution → feedback quantitative architecture** than simply adding more technical indicators.

[1]: https://www.cfainstitute.org/insights/professional-learning/refresher-readings/2026/portfolio-mathematics?utm_source=chatgpt.com "Portfolio Mathematics | CFA Institute"
[2]: https://www.cfainstitute.org/insights/professional-learning/refresher-readings/2026/measuring-managing-market-risk?utm_source=chatgpt.com "Measuring and Managing Market Risk | CFA Institute"
[3]: https://github.com/AshJha0/Quant-Finance-Library?utm_source=chatgpt.com "GitHub - AshJha0/Quant-Finance-Library: Zero-dependency Java quant platform: HFT-grade market data & order path (sub-microsecond, allocation-free), backtesting, FIX 4.4, portfolio optimization, risk analytics, Monte Carlo, reporting. · GitHub"
