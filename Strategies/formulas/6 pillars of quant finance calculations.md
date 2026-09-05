Absolutely. What you have described is essentially a **quantitative-finance mathematical stack** from stochastic processes → statistical prediction → portfolio construction → risk → numerical computation → execution.

Below is a **large formula reference organized by the six pillars**. I will emphasize formulas that are actually useful when building a quantitative research/trading system, not just academic definitions.

> **Notation**
>
> \(S_t\): asset price
> \(r_t\): return
> \(\mu\): drift/expected return
> \(\sigma\): volatility
> \(W_t\): Brownian motion
> \(N(\cdot)\): normal CDF
> \(\Phi(\cdot)\): normal CDF
> \(\phi(\cdot)\): normal PDF
> \(P\): physical/real-world measure
> \(Q\): risk-neutral measure
> \(r_f\): risk-free rate
> \(w\): portfolio weights
> \(\Sigma\): covariance matrix
> \(C\): correlation matrix

---

# 1. Stochastic Modeling & Derivative Pricing — The \(Q\)-Measure World

This pillar is fundamentally about:

$$
\boxed{\text{Price} = E^Q[\text{Discounted Future Cash Flow}]}
$$

---

## 1.1 Brownian Motion

A standard Brownian motion satisfies

$$
W_0=0
$$

$$
W_t-W_s\sim N(0,t-s)
$$

and increments are independent.

Quadratic variation:

$$
(dW_t)^2=dt
$$

$$
dt\,dW_t=0
$$

$$
(dt)^2=0
$$

These relationships are the foundation of stochastic calculus.

---

# 1.2 Geometric Brownian Motion

The classical stock-price model:

$$
dS_t=\mu S_tdt+\sigma S_tdW_t
$$

Solution:

$$
S_t=S_0
\exp\left[
\left(\mu-\frac12\sigma^2\right)t+\sigma W_t
\right]
$$

Log return:

$$
\ln\frac{S_t}{S_0}
=
\left(\mu-\frac12\sigma^2\right)t+\sigma W_t
$$

Therefore:

$$
\ln(S_t/S_0)\sim
N\left[
(\mu-\frac12\sigma^2)t,\sigma^2t
\right]
$$

Expected price:

$$
E[S_t]=S_0e^{\mu t}
$$

Variance:

$$
Var(S_t)=S_0^2e^{2\mu t}(e^{\sigma^2t}-1)
$$

---

# 1.3 Itô's Lemma

For

$$
dS=\mu(S,t)dt+\sigma(S,t)dW
$$

and

$$
V=V(S,t)
$$

then

$$
dV=
\frac{\partial V}{\partial t}dt
+
\frac{\partial V}{\partial S}dS
+
\frac12
\frac{\partial^2V}{\partial S^2}
(dS)^2
$$

Therefore:

$$
dV=
\left(
V_t+\mu S V_S+\frac12\sigma^2S^2V_{SS}
\right)dt
+
\sigma S V_SdW
$$

This produces the Black-Scholes PDE.

---

# 1.4 Risk-Neutral Pricing

Under \(Q\):

$$
dS_t=rS_tdt+\sigma S_tdW_t^Q
$$

Derivative value:

$$
V_t
=
E^Q_t
\left[
e^{-\int_t^T r_sds}V_T
\right]
$$

Constant interest rate:

$$
V_t=e^{-r(T-t)}E^Q[V_T]
$$

---

# 1.5 Black-Scholes

For a European call:

$$
C=S_0N(d_1)-Ke^{-rT}N(d_2)
$$

Put:

$$
P=Ke^{-rT}N(-d_2)-S_0N(-d_1)
$$

where

$$
d_1=
\frac{
\ln(S_0/K)+(r+\frac12\sigma^2)T
}{
\sigma\sqrt T
}
$$

$$
d_2=d_1-\sigma\sqrt T
$$

---

## 1.6 Black-Scholes Greeks

### Delta

Call:

$$
\Delta_C=N(d_1)
$$

Put:

$$
\Delta_P=N(d_1)-1
$$

### Gamma

$$
\Gamma=
\frac{\phi(d_1)}
{S_0\sigma\sqrt T}
$$

### Vega

$$
Vega=
S_0\phi(d_1)\sqrt T
$$

### Theta

Call:

$$
\Theta_C=
-\frac{S_0\phi(d_1)\sigma}{2\sqrt T}
-rKe^{-rT}N(d_2)
$$

Put:

$$
\Theta_P=
-\frac{S_0\phi(d_1)\sigma}{2\sqrt T}
+rKe^{-rT}N(-d_2)
$$

### Rho

Call:

$$
\rho_C=KTe^{-rT}N(d_2)
$$

Put:

$$
\rho_P=-KTe^{-rT}N(-d_2)
$$

---

# 1.7 Greek P&L Approximation

Small changes:

$$
dV\approx
\Delta dS
+
\frac12\Gamma(dS)^2
+
Vega\,d\sigma
+
\Theta\,dt
+
\rho\,dr
$$

More generally:

$$
\Delta V
\approx
\Delta\Delta S
+
\frac12\Gamma(\Delta S)^2
+
Vega\Delta\sigma
+
\Theta\Delta t
+
\rho\Delta r
$$

This is extremely useful for a risk engine.

---

# 1.8 Put-Call Parity

$$
C-P=S_0-Ke^{-rT}
$$

With dividends:

$$
C-P=S_0e^{-qT}-Ke^{-rT}
$$

---

# 1.9 Forward Pricing

No dividends:

$$
F_0=S_0e^{rT}
$$

Continuous dividend yield:

$$
F_0=S_0e^{(r-q)T}
$$

Discrete dividends:

$$
F_0=(S_0-PV(D))e^{rT}
$$

---

# 1.10 Futures Fair Value

Simplified:

$$
F=S_0e^{(r+c-y)T}
$$

where

* \(c\): carrying cost
* \(y\): convenience yield

---

# 1.11 Local Volatility

Dupire-type relationship:

$$
\sigma_{local}^2(K,T)
=
\frac{
\partial_T C
+
(r-q)K\partial_K C
+
qC
}{
\frac12K^2\partial_{KK}C
}
$$

Useful when transforming an implied-volatility surface into a local-volatility model.

---

# 1.12 Heston Model

Variance:

$$
dv_t=
\kappa(\theta-v_t)dt
+
\xi\sqrt{v_t}dW_t^v
$$

Stock:

$$
dS_t=rS_tdt+\sqrt{v_t}S_tdW_t^S
$$

Correlation:

$$
dW_t^SdW_t^v=\rho dt
$$

Parameters:

$$
\kappa,\theta,\xi,\rho,v_0
$$

Feller condition:

$$
2\kappa\theta\geq\xi^2
$$

---

# 1.13 SABR

Forward:

$$
dF_t=\alpha_tF_t^\beta dW_1
$$

Volatility:

$$
d\alpha_t=\nu\alpha_tdW_2
$$

with

$$
dW_1dW_2=\rho dt
$$

Approximate implied volatility:

$$
\sigma_{BS}(F,K)
\approx
\frac{\alpha}{(FK)^{(1-\beta)/2}}
\frac{z}{\chi(z)}
$$

where

$$
z=
\frac{\nu}{\alpha}(FK)^{(1-\beta)/2}\ln(F/K)
$$

---

# 1.14 Short-Rate Models

### Vasicek

$$
dr_t=\kappa(\theta-r_t)dt+\sigma dW_t
$$

Bond price:

$$
P(t,T)=A(t,T)e^{-B(t,T)r_t}
$$

where

$$
B(t,T)=
\frac{1-e^{-\kappa(T-t)}}{\kappa}
$$

---

### CIR

$$
dr_t=
\kappa(\theta-r_t)dt+
\sigma\sqrt{r_t}dW_t
$$

Feller condition:

$$
2\kappa\theta\geq\sigma^2
$$

---

### Hull-White

$$
dr_t=
[\theta(t)-ar_t]dt+\sigma dW_t
$$

More generally:

$$
dr_t=
[\theta(t)-ar_t]dt+\sigma(t)dW_t
$$

---

# 1.15 Zero-Coupon Bond Calculations

Discount factor:

$$
P(0,T)=e^{-yT}
$$

Continuously compounded yield:

$$
y=-\frac{\ln P(0,T)}{T}
$$

Forward rate:

$$
f(T_1,T_2)
=
\frac{
\ln P(0,T_1)-\ln P(0,T_2)
}{
T_2-T_1
}
$$

---

# 1.16 Bond Duration

Macaulay duration:

$$
D_M=
\frac{
\sum_t tPV(CF_t)
}{
P
}
$$

Modified duration:

$$
D_{mod}=
\frac{D_M}{1+y/m}
$$

Price sensitivity:

$$
\frac{\Delta P}{P}
\approx
-D_{mod}\Delta y
$$

Convexity:

$$
Convexity=
\frac1P
\frac{\partial^2P}{\partial y^2}
$$

Price approximation:

$$
\frac{\Delta P}{P}
\approx
-D\Delta y+
\frac12C(\Delta y)^2
$$

---

# 1.17 Credit Risk

Default probability:

$$
PD=P(\tau\leq T)
$$

Expected loss:

$$
EL=PD\times LGD\times EAD
$$

where

$$
LGD=1-Recovery
$$

Hazard rate:

$$
\lambda(t)=
\frac{f(t)}{S(t)}
$$

Survival probability:

$$
S(t)=
e^{-\int_0^t\lambda(u)du}
$$

---

# 1.18 CDS

Approximate CDS spread:

$$
s\approx
\frac{PD\times LGD}{T}
$$

More formally:

$$
PV_{premium}=PV_{protection}
$$

---

# 1.19 XVA

Generic decomposition:

$$
XVA=
CVA+DVA+FVA+KVA+MVA+\cdots
$$

CVA approximately:

$$
CVA=
(1-R)
\int_0^T
DF(t)
EPE(t)
dPD(t)
$$

Expected positive exposure:

$$
EPE(t)=E[\max(V_t,0)]
$$

---

# 2. Statistical Modeling & Alpha Generation — The \(P\)-Measure World

This is particularly important for **your stock-research application**.

The objective changes from:

$$
\boxed{\text{What is the fair derivative price?}}
$$

to:

$$
\boxed{\text{What can we predict about future returns/risk?}}
$$

---

# 2.1 Simple Returns

$$
R_t=\frac{P_t-P_{t-1}}{P_{t-1}}
$$

or

$$
R_t=\frac{P_t}{P_{t-1}}-1
$$

---

# 2.2 Log Returns

$$
r_t=\ln\frac{P_t}{P_{t-1}}
$$

Multi-period:

$$
r_{t,T}=\sum_{i=t+1}^{T}r_i
$$

Arithmetic return:

$$
R_{t,T}=
\prod_i(1+R_i)-1
$$

---

# 2.3 Annualization

Mean:

$$
\mu_{annual}\approx N\mu_{daily}
$$

Volatility:

$$
\sigma_{annual}
=
\sigma_{daily}\sqrt N
$$

Typical \(N=252\).

---

# 2.4 Sample Mean

$$
\bar x=
\frac1n\sum_{i=1}^nx_i
$$

Sample variance:

$$
s^2=
\frac1{n-1}
\sum_{i=1}^n(x_i-\bar x)^2
$$

Standard deviation:

$$
s=\sqrt{s^2}
$$

---

# 2.5 Standard Error

$$
SE(\bar x)=\frac{s}{\sqrt n}
$$

t-statistic:

$$
t=
\frac{\bar x-\mu_0}
{s/\sqrt n}
$$

---

# 2.6 Z-Score

$$
Z_t=
\frac{x_t-\mu_x}{\sigma_x}
$$

Rolling:

$$
Z_t=
\frac{x_t-\mu_{t,n}}
{\sigma_{t,n}}
$$

This is fundamental for:

* mean reversion
* factor signals
* relative valuation
* anomaly detection

---

# 2.7 Covariance

$$
Cov(X,Y)
=
E[(X-E[X])(Y-E[Y])]
$$

Sample:

$$
Cov(X,Y)
=
\frac1{n-1}
\sum_i(x_i-\bar x)(y_i-\bar y)
$$

---

# 2.8 Correlation

$$
\rho_{XY}
=
\frac{Cov(X,Y)}
{\sigma_X\sigma_Y}
$$

---

# 2.9 Beta

$$
\beta_i=
\frac{Cov(R_i,R_m)}
{Var(R_m)}
$$

Regression:

$$
R_i=\alpha_i+\beta_iR_m+\epsilon_i
$$

---

# 2.10 CAPM

$$
E[R_i]=r_f+\beta_i(E[R_m]-r_f)
$$

Alpha:

$$
\alpha_i=
R_i-r_f-\beta_i(R_m-r_f)
$$

---

# 2.11 Sharpe Ratio

$$
Sharpe=
\frac{E[R_p-r_f]}
{\sigma_p}
$$

Annualized:

$$
Sharpe_{annual}
=
\frac{\mu_{daily}-r_{f,daily}}
{\sigma_{daily}}\sqrt{252}
$$

---

# 2.12 Sortino Ratio

$$
Sortino=
\frac{R_p-R_{target}}
{DownsideDeviation}
$$

Downside deviation:

$$
DD=
\sqrt{
\frac1n
\sum_i
\min(R_i-R_{target},0)^2
}
$$

---

# 2.13 Information Ratio

$$
IR=
\frac{R_p-R_b}
{\sigma(R_p-R_b)}
$$

---

# 2.14 Treynor Ratio

$$
Treynor=
\frac{R_p-r_f}{\beta_p}
$$

---

# 2.15 Maximum Drawdown

Running maximum:

$$
M_t=\max_{s\leq t}P_s
$$

Drawdown:

$$
DD_t=
\frac{P_t}{M_t}-1
$$

Maximum drawdown:

$$
MDD=\min_t DD_t
$$

---

# 2.16 Calmar Ratio

$$
Calmar=
\frac{AnnualizedReturn}
{|MDD|}
$$

---

# 2.17 CAGR

$$
CAGR=
\left(\frac{V_T}{V_0}\right)^{1/T}-1
$$

---

# 2.18 Exponential Moving Average

$$
EMA_t=
\alpha x_t+(1-\alpha)EMA_{t-1}
$$

where

$$
\alpha=\frac2{n+1}
$$

---

# 2.19 Simple Moving Average

$$
SMA_n=
\frac1n\sum_{i=0}^{n-1}P_{t-i}
$$

---

# 2.20 EWMA Volatility

$$
\sigma_t^2
=
\lambda\sigma_{t-1}^2
+
(1-\lambda)r_{t-1}^2
$$

---

# 2.21 Historical Volatility

$$
\sigma=
Std(r_1,\ldots,r_n)\sqrt{252}
$$

---

# 2.22 Parkinson Volatility

Using high and low:

$$
\sigma_P^2
=
\frac{1}{4n\ln2}
\sum_{i=1}^n
\left[
\ln(H_i/L_i)
\right]^2
$$

---

# 2.23 Garman-Klass

$$
\sigma^2_{GK}
=
\frac1n
\sum_i
\left[
\frac12(\ln(H_i/L_i))^2
-
(2\ln2-1)(\ln(C_i/O_i))^2
\right]
$$

---

# 2.24 ATR

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
ATR_n=SMA_n(TR)
$$

---

# 2.25 RSI

$$
RS=
\frac{AverageGain}{AverageLoss}
$$

$$
RSI=
100-\frac{100}{1+RS}
$$

---

# 2.26 MACD

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

---

# 2.27 Bollinger Bands

Middle:

$$
MB=SMA_n(P)
$$

Upper:

$$
UB=MB+k\sigma_n
$$

Lower:

$$
LB=MB-k\sigma_n
$$

Bandwidth:

$$
BBW=
\frac{UB-LB}{MB}
$$

%B:

$$
\%B=
\frac{P-LB}{UB-LB}
$$

---

# 2.28 Momentum

$$
Momentum_n=
\frac{P_t}{P_{t-n}}-1
$$

Log momentum:

$$
M_n=\ln(P_t/P_{t-n})
$$

---

# 2.29 Rate of Change

$$
ROC_n=
100
\left(
\frac{P_t}{P_{t-n}}-1
\right)
$$

---

# 2.30 Mean Reversion

Deviation:

$$
D_t=P_t-MA_t
$$

Normalized deviation:

$$
Z_t=
\frac{P_t-MA_t}{\sigma_t}
$$

---

# 2.31 Ornstein-Uhlenbeck

$$
dX_t=
\kappa(\theta-X_t)dt+\sigma dW_t
$$

Expected value:

$$
E[X_t|X_0]
=
\theta+(X_0-\theta)e^{-\kappa t}
$$

Half-life:

$$
t_{1/2}
=
\frac{\ln2}{\kappa}
$$

This is highly relevant to statistical mean-reversion systems.

---

# 2.32 Pairs Trading

Spread:

$$
S_t=P_A-\beta P_B
$$

or

$$
S_t=\ln P_A-\beta\ln P_B
$$

Estimate:

$$
P_A=\alpha+\beta P_B+\epsilon
$$

Spread Z-score:

$$
Z_t=
\frac{S_t-\mu_S}{\sigma_S}
$$

---

# 2.33 Cointegration

Engle-Granger:

$$
Y_t=\alpha+\beta X_t+\epsilon_t
$$

Then test:

$$
\epsilon_t\sim I(0)
$$

If \(X,Y\sim I(1)\), but residual is \(I(0)\), they are cointegrated.

---

# 2.34 ADF Test

Conceptually:

$$
\Delta y_t=
\alpha+\beta t+\gamma y_{t-1}
+
\sum_i\delta_i\Delta y_{t-i}
+\epsilon_t
$$

Null:

$$
H_0:\gamma=0
$$

meaning unit root.

---

# 2.35 Linear Regression

$$
y=X\beta+\epsilon
$$

OLS:

$$
\hat\beta=(X^TX)^{-1}X^Ty
$$

Predicted:

$$
\hat y=X\hat\beta
$$

Residual:

$$
\epsilon=y-\hat y
$$

---

# 2.36 \(R^2\)

$$
R^2=
1-
\frac{SS_{res}}
{SS_{tot}}
$$

---

# 2.37 Adjusted \(R^2\)

$$
R^2_{adj}
=
1-
(1-R^2)
\frac{n-1}{n-k-1}
$$

---

# 2.38 Fama-French Factor Model

Basic:

$$
R_i-r_f=
\alpha_i+
\beta_M(R_M-r_f)
+
\beta_SSMB
+
\beta_HHML
+
\epsilon
$$

Extended versions add:

$$
RMW,\ CMA,\ MOM
$$

---

# 2.39 Factor Exposure

Portfolio factor exposure:

$$
\beta_p=
\sum_iw_i\beta_i
$$

Factor contribution:

$$
FC_i=w_i\beta_i
$$

---

# 2.40 Information Coefficient

$$
IC=
Corr(ActualReturn,PredictedScore)
$$

Rank IC:

$$
IC_{rank}
=
Spearman(prediction,return)
$$

This is one of the most important alpha-quality measurements.

---

# 2.41 IC Information Ratio

$$
ICIR=
\frac{Mean(IC)}
{Std(IC)}
$$

---

# 2.42 Hit Rate

$$
HitRate=
\frac{\#CorrectPredictions}
{\#Predictions}
$$

---

# 2.43 Profit Factor

$$
ProfitFactor=
\frac{GrossProfit}
{GrossLoss}
$$

---

# 2.44 Expectancy

$$
E=
P(win)\times AvgWin
-
P(loss)\times AvgLoss
$$

---

# 2.45 Kelly Criterion

For binary payoff:

$$
f^*=
\frac{bp-q}{b}
$$

where

$$
q=1-p
$$

For continuous assets under simplified assumptions:

$$
f^*=\frac{\mu-r_f}{\sigma^2}
$$

---

# 2.46 Autocorrelation

$$
\rho_k=
\frac{
\sum_{t=k+1}^n
(x_t-\bar x)(x_{t-k}-\bar x)
}{
\sum_{t=1}^n(x_t-\bar x)^2
}
$$

---

# 2.47 Partial Autocorrelation

PACF measures correlation between:

$$
X_t
$$

and

$$
X_{t-k}
$$

after controlling for intermediate lags.

---

# 2.48 AR Model

$$
X_t=
c+
\sum_{i=1}^{p}\phi_iX_{t-i}
+
\epsilon_t
$$

---

# 2.49 MA Model

$$
X_t=
\mu+
\epsilon_t+
\sum_{i=1}^{q}\theta_i\epsilon_{t-i}
$$

---

# 2.50 ARIMA

$$
ARIMA(p,d,q)
$$

After differencing:

$$
\Delta^dX_t=
AR(p)+MA(q)
$$

---

# 2.51 GARCH

$$
r_t=\mu+\epsilon_t
$$

$$
\epsilon_t=\sigma_tz_t
$$

$$
\sigma_t^2=
\omega+
\alpha\epsilon_{t-1}^2+
\beta\sigma_{t-1}^2
$$

Stationarity:

$$
\alpha+\beta<1
$$

Long-run variance:

$$
\sigma^2_\infty=
\frac{\omega}{1-\alpha-\beta}
$$

---

# 2.52 Sharpe Statistical Significance

Approximate:

$$
t\approx Sharpe\sqrt T
$$

But for financial backtests, this naive statistic is often **too optimistic** because of autocorrelation, non-normality and multiple testing.

---

# 2.53 Deflated Sharpe Ratio

Used to adjust observed Sharpe for:

* multiple trials
* non-normal returns
* selection bias

A sophisticated research platform should consider this rather than simply ranking strategies by raw Sharpe.

---

# 2.54 Maximum Adverse Excursion

For each trade:

$$
MAE=
\min_t
\left(
\frac{P_t}{P_{entry}}-1
\right)
$$

Maximum favorable excursion:

$$
MFE=
\max_t
\left(
\frac{P_t}{P_{entry}}-1
\right)
$$

These are excellent for designing stop/exit rules.

---

# 3. Portfolio Optimization & Asset Allocation

This pillar turns individual security forecasts into:

$$
\boxed{\text{Position sizes}}
$$

---

# 3.1 Portfolio Return

$$
R_p=\sum_iw_iR_i
$$

Vector form:

$$
R_p=w^TR
$$

Expected return:

$$
E[R_p]=w^T\mu
$$

---

# 3.2 Portfolio Variance

$$
\sigma_p^2=w^T\Sigma w
$$

Portfolio volatility:

$$
\sigma_p=\sqrt{w^T\Sigma w}
$$

---

# 3.3 Two-Asset Portfolio

$$
\sigma_p^2=
w_1^2\sigma_1^2+
w_2^2\sigma_2^2+
2w_1w_2\rho_{12}\sigma_1\sigma_2
$$

---

# 3.4 Marginal Contribution to Risk

$$
MRC_i=
\frac{\partial\sigma_p}{\partial w_i}
$$

$$
MRC_i=
\frac{(\Sigma w)_i}
{\sigma_p}
$$

---

# 3.5 Component Contribution to Risk

$$
CRC_i=w_iMRC_i
$$

And:

$$
\sum_iCRC_i=\sigma_p
$$

---

# 3.6 Risk Contribution Percentage

$$
RC_i=
\frac{w_iMRC_i}{\sigma_p}
$$

---

# 3.7 Markowitz Optimization

Maximize:

$$
w^T\mu-\frac{\lambda}{2}w^T\Sigma w
$$

subject to:

$$
\sum_iw_i=1
$$

and potentially:

$$
w_i^{min}\leq w_i\leq w_i^{max}
$$

---

# 3.8 Minimum Variance Portfolio

$$
\min_w w^T\Sigma w
$$

subject to:

$$
1^Tw=1
$$

Closed form:

$$
w_{GMV}
=
\frac{\Sigma^{-1}1}
{1^T\Sigma^{-1}1}
$$

---

# 3.9 Target Return Portfolio

$$
\min_w w^T\Sigma w
$$

subject to:

$$
w^T\mu=\mu_p
$$

$$
1^Tw=1
$$

---

# 3.10 Tangency Portfolio

$$
w_T\propto
\Sigma^{-1}(\mu-r_f1)
$$

Normalize:

$$
w_T=
\frac{
\Sigma^{-1}(\mu-r_f1)
}{
1^T\Sigma^{-1}(\mu-r_f1)
}
$$

---

# 3.11 Sharpe Optimization

$$
\max_w
\frac{w^T(\mu-r_f1)}
{\sqrt{w^T\Sigma w}}
$$

---

# 3.12 Black-Litterman

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

where:

* \(P\): view matrix
* \(q\): expected views
* \(\Omega\): view uncertainty
* \(\tau\): uncertainty parameter

---

# 3.13 Risk Parity

Equal risk:

$$
RC_i=\frac{\sigma_p}{N}
$$

Optimization:

$$
\min_w
\sum_i
\left(
RC_i-RC_j
\right)^2
$$

---

# 3.14 Inverse Volatility

$$
w_i=
\frac{1/\sigma_i}
{\sum_j1/\sigma_j}
$$

---

# 3.15 Volatility Targeting

Desired volatility:

$$
\sigma^*
$$

Current:

$$
\sigma_p
$$

Leverage:

$$
L=
\frac{\sigma^*}{\sigma_p}
$$

Position:

$$
w_{target}=Lw
$$

---

# 3.16 Equal Weight

$$
w_i=\frac1N
$$

Simple but surprisingly difficult to beat after costs in some universes.

---

# 3.17 Minimum Correlation Portfolio

Optimize based on:

$$
\min_w
w^TCw
$$

or correlation-aware risk objectives.

---

# 3.18 Covariance Shrinkage

Sample covariance:

$$
S
$$

Shrinkage:

$$
\hat\Sigma
=
\lambda F+(1-\lambda)S
$$

where \(F\) might be:

$$
F=\text{diagonal covariance}
$$

Ledoit-Wolf estimates optimal \(\lambda\).

This is extremely important when:

$$
N_{assets}\approx T_{observations}
$$

---

# 3.19 Portfolio Turnover

$$
Turnover=
\frac12
\sum_i|w_{i,t}-w_{i,t-1}|
$$

Transaction cost:

$$
TC=
\sum_i
c_i|w_{i,t}-w_{i,t-1}|
$$

---

# 3.20 Tracking Error

$$
TE=
Std(R_p-R_b)
$$

Variance:

$$
TE^2=
(w_p-w_b)^T
\Sigma
(w_p-w_b)
$$

---

# 3.21 Active Return

$$
AR=R_p-R_b
$$

---

# 3.22 Active Share

$$
ActiveShare=
\frac12\sum_i|w_{p,i}-w_{b,i}|
$$

---

# 3.23 Portfolio Beta

$$
\beta_p=\sum_iw_i\beta_i
$$

---

# 3.24 Portfolio Alpha

$$
\alpha_p=
R_p-r_f-\beta_p(R_m-r_f)
$$

---

# 3.25 Leverage

$$
Leverage=
\sum_i|w_i|
$$

Gross exposure:

$$
Gross=\sum_i|w_i|
$$

Net exposure:

$$
Net=\sum_iw_i
$$

---

# 3.26 Concentration

Herfindahl index:

$$
HHI=\sum_iw_i^2
$$

Effective number of positions:

$$
N_{eff}=
\frac1{\sum_iw_i^2}
$$

---

# 3.27 Entropy

$$
Entropy=
-\sum_iw_i\ln w_i
$$

Can be used as a diversification constraint.

---

# 3.28 Kelly Portfolio

General form:

$$
w^*=\Sigma^{-1}(\mu-r_f1)
$$

Fractional Kelly:

$$
w_{fractional}=f\,w^*
$$

where typically:

$$
0<f<1
$$

---

# 4. Quantitative Risk Management

The basic objective is:

$$
\boxed{
P(\text{loss}>threshold)
}
$$

---

# 4.1 VaR

VaR at confidence \(c\):

$$
P(L>VaR_c)=1-c
$$

For normally distributed returns:

$$
VaR_c=
z_c\sigma_pV
$$

with appropriate sign convention.

---

# 4.2 Parametric VaR

Portfolio:

$$
VaR=
z_c\sqrt{w^T\Sigma w}V
$$

---

# 4.3 Historical VaR

Sort historical P&L:

$$
L_{(1)}\leq L_{(2)}\leq\cdots
$$

Then:

$$
VaR_c=
Quantile_c(L)
$$

---

# 4.4 Monte Carlo VaR

Simulate:

$$
R^{(1)},R^{(2)},...,R^{(N)}
$$

Calculate:

$$
L^{(i)}
$$

Then:

$$
VaR_c=Quantile_c(L)
$$

---

# 4.5 Expected Shortfall

$$
ES_c=
E[L|L>VaR_c]
$$

Alternative:

$$
ES_c=
\frac1{1-c}
\int_c^1VaR_u\,du
$$

---

# 4.6 Conditional VaR

Often used interchangeably with Expected Shortfall:

$$
CVaR=E[L|L>VaR]
$$

---

# 4.7 Downside Risk

$$
DownsideVariance=
E[
\min(R-R_T,0)^2
]
$$

---

# 4.8 Semi-Deviation

$$
SemiDev=
\sqrt{
E[
\min(R-\bar R,0)^2
]
}
$$

---

# 4.9 Maximum Drawdown

$$
DD_t=
1-\frac{V_t}{\max_{s\leq t}V_s}
$$

---

# 4.10 Ulcer Index

$$
UI=
\sqrt{
\frac1n
\sum_{i=1}^nDD_i^2
}
$$

---

# 4.11 Pain Index

$$
Pain=
\frac1n\sum_iDD_i
$$

---

# 4.12 Recovery Factor

$$
RecoveryFactor=
\frac{NetProfit}
{|MaxDrawdown|}
$$

---

# 4.13 Beta Risk

$$
\beta_i=
\frac{Cov(R_i,R_m)}
{Var(R_m)}
$$

Systematic risk:

$$
\beta_i^2\sigma_m^2
$$

---

# 4.14 Idiosyncratic Risk

From:

$$
R_i=\alpha+\beta R_m+\epsilon
$$

Residual variance:

$$
\sigma_\epsilon^2=Var(\epsilon)
$$

Total variance:

$$
\sigma_i^2=
\beta_i^2\sigma_m^2+
\sigma_\epsilon^2
$$

---

# 4.15 Stress Testing

Scenario P&L:

$$
P\&L_{scenario}
=
\sum_i
\Delta_i\Delta S_i
+
\frac12
\Gamma_i(\Delta S_i)^2
+\cdots
$$

Can extend to:

$$
\Delta\sigma,\Delta r,\Delta FX,\Delta spread
$$

---

# 4.16 Factor Stress

$$
\Delta P
\approx
\sum_k
Exposure_k\Delta Factor_k
$$

---

# 4.17 Correlation Stress

Normal:

$$
\rho_{ij}
$$

Stress:

$$
\rho_{ij}^{stress}
\rightarrow
1
$$

or historically observed crisis correlations.

---

# 4.18 Volatility Shock

$$
\sigma_{stress}
=
\sigma_{current}
+\Delta\sigma
$$

Option P&L:

$$
\Delta V\approx Vega\Delta\sigma
$$

---

# 4.19 Tail Ratio

$$
TailRatio=
\frac{P(R>q_{95})}
{|P(R<q_{05})|}
$$

---

# 4.20 Skewness

$$
Skew=
\frac{E[(X-\mu)^3]}
{\sigma^3}
$$

Sample version:

$$
Skew=
\frac1n
\sum
\left(
\frac{x_i-\bar x}{s}
\right)^3
$$

---

# 4.21 Kurtosis

$$
Kurtosis=
\frac{E[(X-\mu)^4]}
{\sigma^4}
$$

Excess kurtosis:

$$
Kurtosis-3
$$

---

# 4.22 Jarque-Bera

$$
JB=
\frac n6
\left(
S^2+
\frac{(K-3)^2}{4}
\right)
$$

---

# 4.23 EVT — Generalized Pareto Distribution

Exceedances:

$$
Y=X-u
$$

GPD:

$$
G(y)=
1-
\left(
1+\frac{\xi y}{\beta}
\right)^{-1/\xi}
$$

for appropriate support.

---

# 4.24 Extreme Quantile

For tail probability \(p\):

$$
VaR_p
\approx
u+
\frac{\beta}{\xi}
\left[
\left(
\frac{N_u}{Np}
\right)^\xi-1
\right]
$$

---

# 4.25 Expected Loss

$$
EL=PD\times LGD\times EAD
$$

---

# 4.26 Sharpe / Sortino / Calmar / Omega

Omega ratio:

$$
\Omega(\tau)=
\frac{
\int_\tau^\infty[1-F(r)]dr
}{
\int_{-\infty}^\tau F(r)dr
}
$$

---

# 4.27 Risk of Ruin

For simplified independent bets, ruin probability can be approximated from win probability, payoff and bankroll assumptions.

For a practical trading engine, simulation is usually preferable:

$$
P(\min_t Equity_t<Threshold)
$$

---

# 4.28 Margin

Initial margin:

$$
M_{initial}=Notional\times MarginRate
$$

Maintenance margin:

$$
M_{maintenance}=Notional\times MaintenanceRate
$$

Margin utilization:

$$
Utilization=
\frac{UsedMargin}
{AvailableMargin}
$$

---

# 4.29 Liquidity Risk

Amihud illiquidity:

$$
ILLIQ=
\frac1T
\sum_t
\frac{|R_t|}
{DollarVolume_t}
$$

---

# 4.30 Turnover

$$
Turnover=
\frac{Volume}
{SharesOutstanding}
$$

---

# 4.31 Days to Liquidate

$$
DTL=
\frac{PositionSize}
{AverageDailyVolume\times ParticipationRate}
$$

---

# 5. Numerical Methods & Scientific Computing

This is the computational machinery underneath the other pillars.

---

# 5.1 Monte Carlo

Estimate:

$$
E[f(X)]
$$

with:

$$
\hat\mu=
\frac1N\sum_{i=1}^Nf(X_i)
$$

Standard error:

$$
SE=
\frac{s}{\sqrt N}
$$

Confidence interval:

$$
\hat\mu\pm z_{\alpha/2}SE
$$

Error decreases approximately:

$$
O(N^{-1/2})
$$

---

# 5.2 Monte Carlo GBM

Generate:

$$
Z\sim N(0,1)
$$

Then:

$$
S_{t+\Delta t}
=
S_t
\exp
\left[
(\mu-\frac12\sigma^2)\Delta t
+
\sigma\sqrt{\Delta t}Z
\right]
$$

---

# 5.3 Euler-Maruyama

For:

$$
dX_t=a(X_t,t)dt+b(X_t,t)dW_t
$$

use:

$$
X_{t+\Delta t}
=
X_t+
a(X_t,t)\Delta t+
b(X_t,t)\sqrt{\Delta t}Z
$$

---

# 5.4 Milstein

$$
X_{t+\Delta t}
=
X_t+
a\Delta t+
b\Delta W+
\frac12bb_x
[(\Delta W)^2-\Delta t]
$$

Higher numerical accuracy than Euler for many SDEs.

---

# 5.5 Antithetic Variates

For:

$$
Z\sim N(0,1)
$$

simulate both:

$$
Z
$$

and

$$
-Z
$$

Estimator:

$$
\hat\mu=
\frac1N
\sum_i
\frac{f(Z_i)+f(-Z_i)}2
$$

---

# 5.6 Control Variates

If \(Y\) correlated with target \(X\):

$$
X^*=X-\beta(Y-E[Y])
$$

Optimal:

$$
\beta^*=
\frac{Cov(X,Y)}
{Var(Y)}
$$

---

# 5.7 Importance Sampling

Change probability distribution:

$$
E_p[f(X)]
=
E_q
\left[
f(X)\frac{p(X)}{q(X)}
\right]
$$

---

# 5.8 Quasi-Monte Carlo

Use low-discrepancy sequences such as:

* Sobol
* Halton

Instead of pseudo-random samples.

---

# 5.9 Binomial Tree

Up move:

$$
S_u=Su
$$

Down:

$$
S_d=Sd
$$

Risk-neutral probability:

$$
p=
\frac{e^{r\Delta t}-d}
{u-d}
$$

Option value:

$$
V=e^{-r\Delta t}
[pV_u+(1-p)V_d]
$$

---

# 5.10 CRR Binomial Model

$$
u=e^{\sigma\sqrt{\Delta t}}
$$

$$
d=e^{-\sigma\sqrt{\Delta t}}
$$

$$
p=
\frac{e^{r\Delta t}-d}
{u-d}
$$

---

# 5.11 Black-Scholes PDE

$$
\frac{\partial V}{\partial t}
+
rS\frac{\partial V}{\partial S}
+
\frac12\sigma^2S^2
\frac{\partial^2V}{\partial S^2}
-rV=0
$$

---

# 5.12 Finite Difference

Spatial grid:

$$
S_i=i\Delta S
$$

Time grid:

$$
t_n=n\Delta t
$$

First derivative:

$$
V_S
\approx
\frac{V_{i+1}-V_{i-1}}
{2\Delta S}
$$

Second derivative:

$$
V_{SS}
\approx
\frac{
V_{i+1}-2V_i+V_{i-1}
}
{\Delta S^2}
$$

Time:

$$
V_t
\approx
\frac{V_i^{n+1}-V_i^n}{\Delta t}
$$

---

# 5.13 Explicit FDM

General PDE:

$$
V_t+LV=0
$$

Explicit:

$$
V^n=
V^{n+1}+\Delta t\,LV^{n+1}
$$

---

# 5.14 Implicit FDM

$$
V^n=
V^{n+1}+\Delta t\,LV^n
$$

Requires solving a linear system.

---

# 5.15 Crank-Nicolson

$$
V^n=
V^{n+1}
+
\frac{\Delta t}{2}
[
LV^n+LV^{n+1}
]
$$

Often more stable/accurate.

---

# 5.16 Newton-Raphson

Solve:

$$
f(x)=0
$$

Iteration:

$$
x_{n+1}
=
x_n-
\frac{f(x_n)}
{f'(x_n)}
$$

Used extensively for:

* implied volatility
* yield curves
* calibration
* root finding

---

# 5.17 Implied Volatility

Solve:

$$
BS(S,K,r,T,\sigma_{imp})=C_{market}
$$

Newton:

$$
\sigma_{n+1}
=
\sigma_n
-
\frac{
C(\sigma_n)-C_{market}
}{
Vega(\sigma_n)
}
$$

---

# 5.18 Bisection

If:

$$
f(a)f(b)<0
$$

then:

$$
c=\frac{a+b}{2}
$$

and repeatedly halve the interval.

Slower but extremely robust.

---

# 5.19 Gradient Descent

$$
\theta_{t+1}
=
\theta_t-\eta\nabla L(\theta_t)
$$

---

# 5.20 Newton Optimization

$$
\theta_{t+1}
=
\theta_t-
H^{-1}\nabla L
$$

where \(H\) is Hessian.

---

# 5.21 Kalman Filter

State:

$$
x_t=Ax_{t-1}+Bu_t+w_t
$$

Observation:

$$
y_t=Cx_t+v_t
$$

Prediction:

$$
\hat x_{t|t-1}
=
A\hat x_{t-1|t-1}
$$

Covariance:

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

# 5.22 PCA

Covariance matrix:

$$
\Sigma
$$

Solve:

$$
\Sigma v_i=\lambda_i v_i
$$

Variance explained:

$$
VE_i=
\frac{\lambda_i}
{\sum_j\lambda_j}
$$

Useful for:

* factor extraction
* yield curve modeling
* covariance reduction
* statistical arbitrage

---

# 5.23 SVD

$$
X=U\Sigma V^T
$$

Useful for dimensionality reduction and numerical stabilization.

---

# 5.24 Cholesky

For positive-definite covariance:

$$
\Sigma=LL^T
$$

Generate correlated normals:

$$
X=LZ
$$

where:

$$
Z\sim N(0,I)
$$

---

# 5.25 Matrix Inversion

Portfolio calculations frequently require:

$$
\Sigma^{-1}
$$

But computationally, solving:

$$
\Sigma x=b
$$

is usually preferable to explicitly computing \(\Sigma^{-1}\).

---

# 6. Market Microstructure & Algorithmic Execution

This is where the theoretical portfolio becomes **actual orders**.

---

# 6.1 Bid-Ask Spread

$$
Spread=Ask-Bid
$$

Relative spread:

$$
RelativeSpread=
\frac{Ask-Bid}
{Mid}
$$

Midpoint:

$$
Mid=\frac{Bid+Ask}{2}
$$

---

# 6.2 Microprice

One formulation:

$$
Microprice=
\frac{
Ask\times BidSize+
Bid\times AskSize
}{
BidSize+AskSize
}
$$

Order-book imbalance:

$$
OBI=
\frac{BidSize-AskSize}
{BidSize+AskSize}
$$

---

# 6.3 Volume Imbalance

$$
VI=
\frac{V_{buy}-V_{sell}}
{V_{buy}+V_{sell}}
$$

---

# 6.4 Trade Sign

Classify trades:

$$
q_t\in\{-1,+1\}
$$

Then signed volume:

$$
SV_t=q_tV_t
$$

---

# 6.5 VWAP

$$
VWAP=
\frac{
\sum_iP_iV_i
}{
\sum_iV_i
}
$$

---

# 6.6 TWAP

$$
TWAP=
\frac1N
\sum_iP_i
$$

---

# 6.7 Implementation Shortfall

Decision price:

$$
P_0
$$

Execution prices:

$$
P_i
$$

Implementation shortfall:

$$
IS=
Q(P_{exec}-P_0)
$$

for a buy, with appropriate sign convention.

---

# 6.8 Slippage

$$
Slippage=
P_{execution}-P_{benchmark}
$$

Relative:

$$
Slippage\%=
\frac{P_{execution}-P_{benchmark}}
{P_{benchmark}}
$$

---

# 6.9 Market Impact

Simplified:

$$
Impact\propto
\sigma
\sqrt{\frac{Q}{V}}
$$

where:

* \(Q\): order quantity
* \(V\): market volume

---

# 6.10 Participation Rate

$$
POV=
\frac{TraderVolume}
{MarketVolume}
$$

Example:

$$
POV=10\%
$$

means attempt to execute approximately 10% of observed market volume.

---

# 6.11 Almgren-Chriss

Execution trajectory:

$$
x(t)
$$

with inventory:

$$
x(0)=X
$$

$$
x(T)=0
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

A central result is that the optimal execution trajectory balances:

$$
\boxed{
Market\ Impact
\leftrightarrow
Price\ Risk
}
$$

---

# 6.12 Optimal Execution

A simplified objective:

$$
J=
\sum_t
[
Impact_t+
RiskPenalty_t+
Fees_t+
Slippage_t
]
$$

---

# 6.13 Queue Position

Approximate queue position:

$$
QPosition=
\sum_{orders\ ahead}Quantity
$$

Expected fill probability can be modeled as:

$$
P(Fill)=
f(QPosition,TradeRate,CancelRate,Time)
$$

---

# 6.14 Order Book Depth

Depth at level \(k\):

$$
Depth_k=
\sum_{i=1}^kSize_i
$$

Depth imbalance:

$$
DI_k=
\frac{
BidDepth_k-AskDepth_k
}{
BidDepth_k+AskDepth_k
}
$$

---

# 6.15 Amihud Price Impact

$$
ILLIQ=
\frac{|R_t|}
{DollarVolume_t}
$$

---

# 6.16 Kyle's Lambda

Price impact:

$$
\Delta P=\lambda Q
$$

where:

$$
\lambda
=
\frac{\Delta P}{Q}
$$

Higher \(\lambda\) means lower liquidity.

---

# 6.17 Roll Spread Estimator

Using return covariance:

$$
Spread\approx
2\sqrt{-Cov(\Delta P_t,\Delta P_{t-1})}
$$

when covariance is negative.

---

# 6.18 Effective Spread

$$
EffectiveSpread=
2|P_{trade}-Mid|
$$

---

# 6.19 Realized Spread

$$
RealizedSpread=
2q(P_{trade}-Mid_{future})
$$

where \(q=+1\) for buyer-initiated and \(-1\) for seller-initiated trades.

---

# 6.20 Price Impact

$$
PI=
2q(Mid_{future}-Mid_{trade})
$$

---

# 6.21 VPIN

Volume-synchronized probability of informed trading is based on the imbalance between:

$$
BuyVolume
$$

and:

$$
SellVolume
$$

over equal-volume buckets.

A basic imbalance:

$$
VI=
\frac{|V_B-V_S|}
{V_B+V_S}
$$

---

# 6.22 Order Arrival Models

Poisson process:

$$
N(t)\sim Poisson(\lambda t)
$$

Probability:

$$
P[N(t)=k]
=
\frac{(\lambda t)^ke^{-\lambda t}}
{k!}
$$

Expected arrivals:

$$
E[N(t)]=\lambda t
$$

---

# 6.23 Exponential Interarrival Time

$$
T\sim Exponential(\lambda)
$$

PDF:

$$
f(t)=\lambda e^{-\lambda t}
$$

Expected waiting time:

$$
E[T]=\frac1\lambda
$$

---

# 6.24 Hawkes Process

Intensity:

$$
\lambda_t=
\mu+
\sum_{t_i<t}
\alpha e^{-\beta(t-t_i)}
$$

This models clustered order/trade arrivals.

---

# 6.25 Execution Cost Decomposition

Total trading cost can be decomposed as:

$$
TCA=
Commission+
SpreadCost+
MarketImpact+
Slippage+
OpportunityCost
$$

---

# 6.26 Opportunity Cost

For unfilled quantity:

$$
OC=
Q_{unfilled}
(P_{future}-P_{decision})
$$

with sign adjusted for buy/sell.

---

# 6.27 Arrival Price

For a buy:

$$
Cost=
\sum_iQ_i(P_i-P_{arrival})
$$

---

# 6.28 Participation Constraints

$$
\frac{Q_t}{Volume_t}
\leq
POV_{max}
$$

---

# 6.29 Position Capacity

Approximation:

$$
Capacity\propto
ADV\times
MaxParticipation
$$

For example:

$$
Capacity=
ADV\times
POV\times
DaysAvailable
$$

---

# 6.30 Turnover Cost

Portfolio transition:

$$
TC=
\sum_i
c_i|w_{i,new}-w_{i,old}|
$$

A more realistic model:

$$
TC=
\sum_i
[
Commission_i+
Spread_i+
Impact_i
]
$$

---

# 7. Cross-Pillar Calculations

This is where a **real quantitative stock system** becomes much more powerful.

---

## 7.1 Expected Return → Risk-Adjusted Score

One possible alpha score:

$$
Score_i=
\frac{E[R_i]-r_f}
{\sigma_i}
$$

But you can improve it:

$$
Score_i=
\frac{
E[R_i]-r_f-TC_i
}{
\sigma_i
}
$$

---

# 7.2 Expected Alpha

$$
Alpha_i=
E[R_i]-
[
r_f+\beta_i(E[R_m]-r_f)
]
$$

---

# 7.3 Alpha / Volatility

$$
AlphaRiskRatio=
\frac{Alpha_i}{\sigma_i}
$$

---

# 7.4 Alpha / Drawdown

$$
AlphaDD=
\frac{ExpectedAlpha}
{ExpectedDrawdown}
$$

---

# 7.5 Signal-to-Noise Ratio

$$
SNR=
\frac{\mu}{\sigma}
$$

For a prediction:

$$
SNR=
\frac{ExpectedSignal}
{PredictionError}
$$

---

# 7.6 Information Coefficient → Expected Portfolio Sharpe

A useful conceptual relationship:

$$
IR\approx
IC\times\sqrt{Breadth}
$$

where breadth is the number of independent bets.

This is related to the fundamental law of active management.

---

# 7.7 Forecast Combination

If multiple models produce:

$$
\hat R_1,\hat R_2,\ldots,\hat R_k
$$

combined forecast:

$$
\hat R=
\sum_jw_j\hat R_j
$$

subject to:

$$
\sum_jw_j=1
$$

Optimally:

$$
w\propto\Sigma_{forecast}^{-1}\mu_{forecast}
$$

---

# 7.8 Bayesian Updating

Prior:

$$
P(\theta)
$$

Likelihood:

$$
P(Data|\theta)
$$

Posterior:

$$
P(\theta|Data)
\propto
P(Data|\theta)P(\theta)
$$

---

# 7.9 Bayesian Expected Return

$$
E[\mu|Data]
$$

can replace raw historical:

$$
\bar R
$$

to reduce estimation error.

---

# 7.10 Probability of Positive Return

If:

$$
R\sim N(\mu,\sigma^2)
$$

then:

$$
P(R>0)
=
\Phi\left(\frac{\mu}{\sigma}\right)
$$

---

# 7.11 Probability of Hitting a Target

For:

$$
R\sim N(\mu,\sigma^2)
$$

$$
P(R>R^*)
=
1-
\Phi
\left(
\frac{R^*-\mu}{\sigma}
\right)
$$

---

# 7.12 Expected Utility

Mean-variance:

$$
U=
E[R]-\frac{\lambda}{2}Var(R)
$$

CRRA:

$$
U(W)=
\frac{W^{1-\gamma}}{1-\gamma}
$$

Log utility:

$$
U(W)=\ln W
$$

---

# 7.13 Expected Shortfall Adjusted Score

$$
Score=
\frac{ExpectedReturn}
{ES_{95}}
$$

---

# 7.14 Return / VaR

$$
ReturnVaRRatio=
\frac{ExpectedReturn}
{VaR_{95}}
$$

---

# 7.15 Return / CVaR

$$
ReturnCVaR=
\frac{ExpectedReturn}
{CVaR_{95}}
$$

---

# 7.16 Risk-Adjusted Alpha Score

For example:

$$
Score_i=
w_1Z(\alpha_i)
+
w_2Z(Sharpe_i)
-
w_3Z(Vol_i)
-
w_4Z(MDD_i)
-
w_5Z(TC_i)
$$

This kind of composite scoring is particularly applicable to a stock-ranking system.

---

# 8. Fundamental Quantitative Finance Calculations

For a stock-analysis system, the six pillars above should usually be supplemented with a fundamental/valuation layer.

---

## 8.1 EPS

$$
EPS=
\frac{NetIncome-PreferredDividends}
{WeightedAverageShares}
$$

---

## 8.2 P/E

$$
PE=
\frac{Price}{EPS}
$$

Forward P/E:

$$
ForwardPE=
\frac{Price}
{ExpectedFutureEPS}
$$

---

## 8.3 PEG

$$
PEG=
\frac{PE}
{EPSGrowthRate}
$$

---

## 8.4 Earnings Yield

$$
EY=
\frac{EPS}{Price}
=
\frac1{PE}
$$

---

## 8.5 Price/Sales

$$
P/S=
\frac{MarketCap}
{Revenue}
$$

---

## 8.6 EV

$$
EV=
MarketCap+
Debt+
PreferredStock+
MinorityInterest
-Cash
$$

---

## 8.7 EV/EBITDA

$$
EV/EBITDA=
\frac{EV}{EBITDA}
$$

---

## 8.8 Free Cash Flow

$$
FCF=
OperatingCashFlow-CapEx
$$

---

## 8.9 FCF Yield

$$
FCFYield=
\frac{FCF}{MarketCap}
$$

---

## 8.10 ROE

$$
ROE=
\frac{NetIncome}
{AverageShareholdersEquity}
$$

---

## 8.11 ROA

$$
ROA=
\frac{NetIncome}
{AverageTotalAssets}
$$

---

## 8.12 ROIC

$$
ROIC=
\frac{NOPAT}
{InvestedCapital}
$$

NOPAT:

$$
NOPAT=EBIT(1-T)
$$

---

## 8.13 WACC

$$
WACC=
\frac{E}{D+E}R_e
+
\frac{D}{D+E}R_d(1-T)
$$

Cost of equity via CAPM:

$$
R_e=
R_f+\beta(E[R_m]-R_f)
$$

---

# 9. DCF

Enterprise value:

$$
EV=
\sum_{t=1}^{T}
\frac{FCF_t}{(1+WACC)^t}
+
\frac{TV}{(1+WACC)^T}
$$

Terminal value using Gordon Growth:

$$
TV=
\frac{FCF_{T+1}}
{WACC-g}
$$

where:

$$
FCF_{T+1}=FCF_T(1+g)
$$

Equity value:

$$
EquityValue=
EV-Debt+Cash
$$

Per-share:

$$
FairValue=
\frac{EquityValue}
{SharesOutstanding}
$$

---

# 10. Earnings Growth

Historical CAGR:

$$
CAGR=
\left(
\frac{EPS_T}{EPS_0}
\right)^{1/T}-1
$$

Forward earnings growth:

$$
g=
\frac{EPS_{future}-EPS_{current}}
{EPS_{current}}
$$

---

# 11. Earnings Surprise

$$
Surprise=
\frac{Actual-EPS_{estimate}}
{|EPS_{estimate}|}
$$

---

# 12. Revenue Growth

$$
RevenueGrowth=
\frac{Revenue_t-Revenue_{t-1}}
{Revenue_{t-1}}
$$

---

# 13. Margin

Gross margin:

$$
GM=
\frac{Revenue-COGS}
{Revenue}
$$

Operating margin:

$$
OM=
\frac{OperatingIncome}
{Revenue}
$$

Net margin:

$$
NM=
\frac{NetIncome}
{Revenue}
$$

---

# 14. Composite Quantitative Stock Score

A practical architecture could eventually produce something like:

$$
\boxed{
QScore=
\alpha A+
\beta V+
\gamma M+
\delta Q+
\epsilon R+
\zeta L
}
$$

where:

* \(A\) = Alpha
* \(V\) = Valuation
* \(M\) = Momentum
* \(Q\) = Quality
* \(R\) = Risk
* \(L\) = Liquidity

After normalization:

$$
Z_i=
\frac{X_i-\mu_X}{\sigma_X}
$$

Then:

$$
QScore_i=
\sum_k w_kZ_{ik}
$$

---

# 15. A More Sophisticated Quant Research Pipeline

For the kind of quantitative stock application you've described previously, I would structure the mathematical pipeline approximately as:

```text
                    MARKET DATA
                        │
          ┌─────────────┴─────────────┐
          │                           │
      FUNDAMENTAL                  PRICE DATA
          │                           │
          ▼                           ▼
     Valuation                    Technical
     Quality                      Momentum
     Growth                       Volatility
     Profitability                Microstructure
          │                           │
          └─────────────┬─────────────┘
                        ▼
                 FEATURE ENGINE
                        │
                        ▼
              STATISTICAL MODELS
                        │
            ┌───────────┼───────────┐
            ▼           ▼           ▼
         Factor       ML/AI       Regime
         Models       Models      Models
            │           │           │
            └───────────┼───────────┘
                        ▼
                  ALPHA FORECAST
                        │
                        ▼
                RISK ADJUSTMENT
                        │
            ┌───────────┼───────────┐
            ▼           ▼           ▼
           VaR          ES          DD
            │           │           │
            └───────────┼───────────┘
                        ▼
               PORTFOLIO OPTIMIZER
                        │
                        ▼
                POSITION SIZING
                        │
                        ▼
              EXECUTION OPTIMIZER
                        │
            ┌───────────┼───────────┐
            ▼           ▼           ▼
          VWAP        TWAP       POV/AC
            │           │           │
            └───────────┼───────────┘
                        ▼
                  ACTUAL FILLS
                        │
                        ▼
                 TCA / FEEDBACK
                        │
                        └──────────────► MODEL UPDATE
```

---

# 16. The Most Important Formula Families for Your Stock System

If your goal is specifically to evolve your existing **quantitative stock research application into a complete research → portfolio → execution platform**, I would prioritize these rather than implementing every formula equally.

### Tier 1 — Essential

$$
\boxed{
Return,\ Volatility,\ Covariance,\ Correlation,\ Beta
}
$$

$$
\boxed{
Sharpe,\ Sortino,\ MDD,\ CAGR,\ Calmar
}
$$

$$
\boxed{
Momentum,\ RSI,\ MACD,\ Bollinger,\ ATR
}
$$

$$
\boxed{
ZScore,\ MeanReversion,\ HalfLife
}
$$

$$
\boxed{
Alpha,\ FactorExposure,\ IC,\ ICIR
}
$$

$$
\boxed{
VaR,\ ES,\ StressTest
}
$$

$$
\boxed{
PortfolioVariance=w^T\Sigma w
}
$$

$$
\boxed{
RiskContribution_i=
\frac{w_i(\Sigma w)_i}{\sigma_p}
}
$$

$$
\boxed{
Turnover=
\frac12\sum_i|w_i-w_i^{old}|
}
$$

$$
\boxed{
TransactionCost=
Spread+Commission+Impact+Slippage
}
$$

---

# 17. Tier 2 — Very Important for a Serious Quant Platform

### Regime detection

$$
P(S_t|S_{t-1})
$$

Hidden Markov Models:

$$
P(S_t|S_{t-1})
$$

and:

$$
P(X_t|S_t)
$$

### GARCH

$$
\sigma_t^2=
\omega+
\alpha\epsilon_{t-1}^2+
\beta\sigma_{t-1}^2
$$

### Cointegration

$$
Y_t-\beta X_t
$$

### PCA

$$
\Sigma v_i=\lambda_iv_i
$$

### Shrinkage covariance

$$
\hat\Sigma=
\lambda F+(1-\lambda)S
$$

### Black-Litterman

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

### Volatility targeting

$$
Leverage=
\frac{\sigma_{target}}
{\sigma_{forecast}}
$$

---

# 18. Tier 3 — Execution Layer

For the execution system you were considering adding to your application:

$$
\boxed{VWAP}
$$

$$
\boxed{TWAP}
$$

$$
\boxed{POV}
$$

$$
\boxed{Implementation\ Shortfall}
$$

$$
\boxed{Almgren-Chriss}
$$

$$
\boxed{Market\ Impact}
$$

$$
\boxed{Order\ Book\ Imbalance}
$$

$$
\boxed{Microprice}
$$

$$
\boxed{Effective\ Spread}
$$

$$
\boxed{Realized\ Spread}
$$

$$
\boxed{TCA}
$$

These are what bridge your current **"this stock should be bought"** signal into **"how, when, and at what price should I actually buy it?"**

---

## One important architectural distinction

There is a very important conceptual separation among the six pillars:

| Pillar                 | Primary question               | Mathematical objective      |       |
| ---------------------- | ------------------------------ | --------------------------- | ----- |
| **Stochastic Pricing** | What is this derivative worth? | \(E^Q[Discounted\ Payoff]\) |       |
| **Statistical Alpha**  | What will happen?              | (E^P[R_{t+1}                | X_t]) |
| **Portfolio**          | How much should I own?         | Optimize \(w\)              |       |
| **Risk**               | What can go wrong?             | \(P(L>x)\), \(ES\), stress  |       |
| **Numerical**          | How do I calculate it?         | Approximation/optimization  |       |
| **Execution**          | How do I trade it?             | Minimize cost/impact/risk   |       |

And for a modern equity quant system, the full mathematical chain can be summarized as:

$$
\boxed{
Data
\rightarrow
Features
\rightarrow
Forecast
\rightarrow
Alpha
\rightarrow
Risk
\rightarrow
Portfolio
\rightarrow
Position
\rightarrow
Execution
\rightarrow
Fill
\rightarrow
TCA
\rightarrow
Feedback
}
$$

The **most important point for your existing application** is that these formulas should not simply become a giant collection of indicators. They should form a dependency graph. For example:

$$
\text{Price}
\rightarrow
\text{Return}
\rightarrow
\text{Volatility}
\rightarrow
\text{Covariance}
\rightarrow
\text{Portfolio Risk}
$$

while:

$$
\text{Price}
\rightarrow
\text{Momentum/Mean Reversion}
\rightarrow
\text{Alpha}
\rightarrow
\text{Expected Return}
\rightarrow
\text{Position Size}
$$

and finally:

$$
\text{Position Size}
\rightarrow
\text{ADV/Liquidity}
\rightarrow
\text{Market Impact}
\rightarrow
\text{Execution Schedule}
\rightarrow
\text{Actual P\&L}
$$

That architecture is much more powerful than calculating hundreds of indicators independently.

If you want to take this to the next level, the natural next artifact would be a **"Quant Finance Formula Master Catalog"** containing roughly **300–500 formulas**, organized into **Market Data, Returns, Technical Indicators, Statistics, Factor Models, Valuation, Alpha, Time Series, ML, Portfolio Optimization, Risk, Derivatives, Volatility, Fixed Income, Credit, Monte Carlo, Numerical Methods, Microstructure, Execution, Backtesting and Performance Attribution**, with each formula tagged by **inputs → calculation → output → purpose → recommended use in your application**.
