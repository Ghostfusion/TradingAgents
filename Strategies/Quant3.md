There is no finite list of **all** calculations used by quantitative traders: “quant trading” spans market making, statistical arbitrage, systematic macro, options/volatility, execution, portfolio construction, and ML. But below is a practical formula map of the calculations that recur across real research and trading systems—returns, signals, forecasts, sizing, transaction costs, risk, optimization, and derivatives.

Quants use mathematical models and algorithms on market data to identify and execute trades; the exact formula set depends heavily on asset class, time horizon, and strategy. [investopedia](https://www.investopedia.com/terms/q/quantitative-trading.asp)

## Notation

| Symbol | Meaning |
|---|---|
| \(P_t\) | Price at time \(t\) |
| \(r_t\) | Return over period \(t\) |
| \(w\) | Portfolio weights |
| \(\mu\) | Expected return / mean |
| \(\sigma\) | Volatility / standard deviation |
| \(\Sigma\) | Covariance matrix |
| \(R_f\) | Risk-free rate |
| \(N(\cdot)\) | Standard-normal cumulative distribution function |
| \(S_0\) | Underlying price now |
| \(K\) | Option strike |
| \(T\) | Time to expiry in years |
| \(\epsilon_t\) | Random innovation/residual |
| \(q_t\) | Position or trade quantity |

Unless noted, use **decimal** returns: 1% = \(0.01\).

## Price, Return, and Compounding

### Simple and log returns

\[
r_t = \frac{P_t-P_{t-1}}{P_{t-1}}
= \frac{P_t}{P_{t-1}}-1
\]

\[
\ell_t = \ln\left(\frac{P_t}{P_{t-1}}\right)
\]

Simple returns compound exactly:

\[
P_T = P_0\prod_{t=1}^{T}(1+r_t)
\]

Cumulative return:

\[
R_{\text{cum}} = \prod_{t=1}^{T}(1+r_t)-1
\]

Log returns add over time:

\[
\ell_{0,T} = \sum_{t=1}^{T}\ell_t
= \ln\left(\frac{P_T}{P_0}\right)
\]

Conversion:

\[
r_t=e^{\ell_t}-1
\]

### Annualization

For \(N\) observations per year—often 252 daily sessions:

\[
\mu_{\text{ann}} \approx N\bar r
\]

\[
\sigma_{\text{ann}} \approx \sigma_{\text{period}}\sqrt{N}
\]

For a total return over \(Y\) years:

\[
\text{CAGR}
=
\left(\frac{V_T}{V_0}\right)^{1/Y}-1
\]

### Present value and discounting

Discrete compounding:

\[
PV = \frac{FV}{(1+r)^T}
\]

Continuous compounding:

\[
PV=FV e^{-rT}
\]

\[
FV=PV e^{rT}
\]

Exponentials and logarithms are foundational in finance, particularly for continuous compounding and likelihood-based estimation. [dummies](https://www.dummies.com/article/business-careers-money/business/accounting/general-accounting/quantitative-finance-dummies-cheat-sheet-226727/)

## Descriptive Statistics and Dependence

### Mean, variance, and volatility

Sample mean:

\[
\bar r = \frac{1}{n}\sum_{t=1}^{n}r_t
\]

Sample variance:

\[
s^2=\frac{1}{n-1}\sum_{t=1}^{n}(r_t-\bar r)^2
\]

Sample volatility:

\[
s=\sqrt{s^2}
\]

Downside deviation relative to target \(r^\star\):

\[
\sigma_{\text{down}}
=
\sqrt{
\frac{1}{n}
\sum_{t=1}^{n}
\min(r_t-r^\star,0)^2
}
\]

### Covariance and correlation

\[
\operatorname{Cov}(X,Y)
=
\frac{1}{n-1}
\sum_{t=1}^{n}(X_t-\bar X)(Y_t-\bar Y)
\]

\[
\rho_{X,Y}
=
\frac{\operatorname{Cov}(X,Y)}
{\sigma_X\sigma_Y}
\]

Correlation matrix:

\[
\mathbf{R}
=
\mathbf{D}^{-1/2}\Sigma\mathbf{D}^{-1/2}
\]

where \(\mathbf{D}\) is the diagonal matrix of variances.

### Higher moments

Skewness:

\[
\operatorname{Skew}(r)
=
\frac{
\frac{1}{n}\sum_{t=1}^{n}(r_t-\bar r)^3
}{s^3}
\]

Excess kurtosis:

\[
\operatorname{ExKurt}(r)
=
\frac{
\frac{1}{n}\sum_{t=1}^{n}(r_t-\bar r)^4
}{s^4}
-3
\]

These matter because financial-return distributions often have asymmetric tails and more extreme events than a normal distribution implies.

### Autocorrelation

Lag-\(k\) autocorrelation:

\[
\rho_k
=
\operatorname{Corr}(r_t,r_{t-k})
\]

A basic mean-reversion or momentum diagnostic is often simply whether estimated \(\rho_1\) is negative or positive, after accounting for costs and statistical uncertainty.

## Signal Construction

### Moving averages

Simple moving average (SMA):

\[
\operatorname{SMA}_t^{(n)}
=
\frac{1}{n}
\sum_{i=0}^{n-1}P_{t-i}
\]

Exponential moving average (EMA):

\[
\operatorname{EMA}_t
=
\alpha P_t+(1-\alpha)\operatorname{EMA}_{t-1}
\]

\[
\alpha=\frac{2}{n+1}
\]

A common trend signal:

\[
s_t
=
\operatorname{sign}
\left(
\operatorname{SMA}^{(\text{fast})}_t
-
\operatorname{SMA}^{(\text{slow})}_t
\right)
\]

### Momentum

Lookback return:

\[
M_t^{(L)}
=
\frac{P_t}{P_{t-L}}-1
\]

Log momentum:

\[
M_t^{(L)}
=
\ln P_t-\ln P_{t-L}
\]

Volatility-scaled momentum:

\[
z_t^{\text{mom}}
=
\frac{
\ln(P_t/P_{t-L})
}{
\hat{\sigma}_t\sqrt{L}
}
\]

### Mean reversion and z-scores

Rolling z-score:

\[
z_t
=
\frac{x_t-\mu_t^{(L)}}{\sigma_t^{(L)}}
\]

A simple contrarian signal:

\[
s_t=-z_t
\]

For an asset price relative to a rolling mean:

\[
z_t
=
\frac{P_t-\operatorname{SMA}_t^{(L)}}
{\operatorname{Std}_t^{(L)}(P)}
\]

Typical rule logic—not a guaranteed strategy:

\[
z_t>2 \Rightarrow \text{consider short bias}
\]

\[
z_t<-2 \Rightarrow \text{consider long bias}
\]

The actual trading model needs entry, exit, exposure, cost, and risk rules; a z-score alone is not an edge.

### Relative strength index

Define average gains and losses over \(n\) periods:

\[
RS=\frac{\text{Avg Gain}}{\text{Avg Loss}}
\]

\[
RSI=100-\frac{100}{1+RS}
\]

### Bollinger bands

\[
\text{Middle}_t=\operatorname{SMA}^{(n)}_t
\]

\[
\text{Upper}_t=\text{Middle}_t+k\sigma_t^{(n)}
\]

\[
\text{Lower}_t=\text{Middle}_t-k\sigma_t^{(n)}
\]

### Cross-sectional factor score

For factor exposure \(x_{i,t}\) across assets \(i=1,\dots,N\):

\[
z_{i,t}
=
\frac{x_{i,t}-\bar x_t}{s_{x,t}}
\]

Composite score:

\[
\text{Score}_{i,t}
=
\sum_{k=1}^{K} a_k z_{i,k,t}
\]

A simple market-neutral portfolio can buy high-score assets and short low-score assets after sector, beta, liquidity, and turnover controls.

## Time-Series Models and Forecasting

### AR(1)

\[
x_t=c+\phi x_{t-1}+\epsilon_t
\]

- \(|\phi|<1\): stationary process.
- \(\phi>0\): persistence / short-term momentum tendency.
- \(\phi<0\): tendency toward reversal.

An AR(1) model is a standard time-series baseline. [linkedin](https://www.linkedin.com/posts/prateek964_quantitativefinance-machinelearning-datascience-activity-7490063746699284480-JoTq)

### ARMA and ARIMA

\[
x_t
=
c+\sum_{i=1}^{p}\phi_i x_{t-i}
+
\epsilon_t
+
\sum_{j=1}^{q}\theta_j\epsilon_{t-j}
\]

ARIMA adds differencing to model nonstationary levels:

\[
(1-L)^d x_t=\text{ARMA}(p,q)
\]

where \(L\) is the lag operator.

### Exponentially weighted volatility

\[
\sigma_t^2
=
\lambda \sigma_{t-1}^2
+
(1-\lambda)r_{t-1}^2
\]

This is EWMA volatility. A conventional daily RiskMetrics-style decay parameter is often near \(0.94\), but it should be calibrated rather than blindly adopted.

### GARCH(1,1)

\[
r_t=\mu+\epsilon_t
\]

\[
\epsilon_t=\sigma_t z_t
\]

\[
\sigma_t^2
=
\omega+\alpha\epsilon_{t-1}^2+\beta\sigma_{t-1}^2
\]

GARCH models volatility clustering: large moves tend to be followed by further large moves.

### Ornstein–Uhlenbeck process

Used frequently for mean-reverting spreads:

\[
dX_t
=
\kappa(\theta-X_t)dt+\sigma dW_t
\]

Discrete approximation:

\[
X_{t+\Delta t}
=
\theta
+
e^{-\kappa\Delta t}(X_t-\theta)
+
\epsilon_t
\]

Half-life of mean reversion:

\[
t_{1/2}
=
\frac{\ln 2}{\kappa}
\]

### Kalman filter state-space model

Observation:

\[
y_t=H_tx_t+v_t
\]

State transition:

\[
x_t=F_tx_{t-1}+w_t
\]

This is useful for time-varying hedge ratios, latent fair value, dynamic betas, and online signal estimation.

### Linear regression and OLS

\[
y=X\beta+\epsilon
\]

\[
\hat{\beta}
=
(X^\top X)^{-1}X^\top y
\]

Predicted value:

\[
\hat y=X\hat\beta
\]

Residual:

\[
\hat\epsilon=y-\hat y
\]

Coefficient of determination:

\[
R^2
=
1-\frac{\sum(y_t-\hat y_t)^2}
{\sum(y_t-\bar y)^2}
\]

### Ridge and Lasso regression

Ridge:

\[
\hat\beta_{\text{ridge}}
=
\arg\min_\beta
\left[
\|y-X\beta\|_2^2
+
\lambda\|\beta\|_2^2
\right]
\]

Lasso:

\[
\hat\beta_{\text{lasso}}
=
\arg\min_\beta
\left[
\|y-X\beta\|_2^2
+
\lambda\|\beta\|_1
\right]
\]

Ridge stabilizes correlated features; Lasso can set weak feature coefficients to zero.

## Statistical Arbitrage and Pairs Trading

### Hedge ratio via regression

For two related assets:

\[
y_t=\alpha+\beta x_t+\epsilon_t
\]

Hedge ratio:

\[
\hat\beta
=
\frac{\operatorname{Cov}(x,y)}
{\operatorname{Var}(x)}
\]

Spread:

\[
s_t=y_t-\hat\alpha-\hat\beta x_t
\]

Then calculate a rolling z-score of the spread:

\[
z_t^{\text{spread}}
=
\frac{s_t-\bar s_t}{\sigma_{s,t}}
\]

### Cointegration relationship

\[
y_t-\beta x_t \sim I(0)
\]

Even if \(x_t\) and \(y_t\) themselves are nonstationary price series, the residual/spread may be stationary. A valid cointegration test is important; correlation alone is not enough.

### Error-correction model

\[
\Delta y_t
=
\alpha
+
\gamma(y_{t-1}-\beta x_{t-1})
+
\delta \Delta x_t
+
\epsilon_t
\]

If \(\gamma<0\), deviations from equilibrium tend to correct.

### Half-life from an ADF-style regression

Estimate:

\[
\Delta s_t=\alpha+\beta s_{t-1}+\epsilon_t
\]

Then approximate:

\[
t_{1/2}
=
-\frac{\ln 2}{\beta}
\]

This approximation applies when the fitted \(\beta<0\).

## Portfolio Construction and Position Sizing

### Portfolio return

\[
R_{p,t}
=
\sum_{i=1}^{N}w_{i,t}r_{i,t}
=
w_t^\top r_t
\]

Expected portfolio return:

\[
E[R_p]=w^\top\mu
\]

### Portfolio variance

\[
\sigma_p^2
=
w^\top\Sigma w
\]

Expanded:

\[
\sigma_p^2
=
\sum_{i=1}^{N}
\sum_{j=1}^{N}
w_iw_j\operatorname{Cov}(r_i,r_j)
\]

This is the core diversification calculation. [linkedin](https://www.linkedin.com/posts/riskhuborg_quantfinance-financialengineering-mathematics-activity-7484810240744439808-IqRE)

### Inverse-volatility weights

\[
\tilde w_i=\frac{1}{\hat\sigma_i}
\]

\[
w_i=\frac{\tilde w_i}{\sum_j\tilde w_j}
\]

### Risk contribution

Marginal contribution to portfolio volatility:

\[
\operatorname{MRC}_i
=
\frac{(\Sigma w)_i}{\sigma_p}
\]

Component risk contribution:

\[
\operatorname{RC}_i
=
w_i\frac{(\Sigma w)_i}{\sigma_p}
\]

\[
\sum_i \operatorname{RC}_i=\sigma_p
\]

Risk parity seeks approximately equal contributions:

\[
\operatorname{RC}_1
\approx
\operatorname{RC}_2
\approx
\dots
\approx
\operatorname{RC}_N
\]

### Volatility targeting

For target annualized volatility \(\sigma^\star\):

\[
\text{Leverage}_t
=
\frac{\sigma^\star}{\hat\sigma_t}
\]

Then:

\[
w_t^{\text{scaled}}
=
\frac{\sigma^\star}{\hat\sigma_t}w_t
\]

Practical implementations impose leverage caps, liquidity limits, and crisis overrides.

### Kelly criterion

For a binary wager with win probability \(p\), loss probability \(q=1-p\), and net odds \(b\):

\[
f^\star=\frac{bp-q}{b}
\]

For a multi-asset approximation:

\[
w^\star \approx \Sigma^{-1}\mu
\]

Full Kelly is often too aggressive under estimation error; many systematic traders use fractional Kelly.

### Mean-variance optimization

\[
\max_w
\left(
w^\top\mu-\frac{\gamma}{2}w^\top\Sigma w
\right)
\]

Or minimum-variance form:

\[
\min_w w^\top\Sigma w
\]

subject to constraints such as:

\[
\mathbf{1}^\top w=1
\]

\[
w^\top\mu=\mu^\star
\]

\[
w_{\min}\leq w_i\leq w_{\max}
\]

### Maximum Sharpe portfolio

Ignoring constraints:

\[
w^\star \propto \Sigma^{-1}(\mu-R_f\mathbf{1})
\]

### Regularized optimization with trading costs

A more realistic objective:

\[
\max_w
\left[
w^\top\hat\mu
-\frac{\gamma}{2}w^\top\hat\Sigma w
-\lambda_{\text{turn}}\|w-w_{\text{old}}\|_1
-\lambda_{\text{impact}}\|w-w_{\text{old}}\|_2^2
\right]
\]

The final two terms discourage excessive turnover and market impact.

## Performance and Risk Metrics

### Sharpe ratio

\[
\text{Sharpe}
=
\frac{\bar R_p-R_f}{\sigma_p}
\]

Annualized from daily returns:

\[
\text{Sharpe}_{\text{ann}}
=
\sqrt{252}
\cdot
\frac{\bar r_d-r_{f,d}}{\sigma_d}
\]

The usual Sharpe formulation compares excess portfolio return with portfolio volatility. [linkedin](https://www.linkedin.com/posts/riskhuborg_quantfinance-financialengineering-mathematics-activity-7484810240744439808-IqRE)

### Sortino ratio

\[
\text{Sortino}
=
\frac{\bar R_p-R_f}
{\sigma_{\text{down}}}
\]

### Information ratio

\[
\text{IR}
=
\frac{\overline{R_p-R_b}}
{\sigma(R_p-R_b)}
\]

where \(R_b\) is a benchmark return.

### Maximum drawdown

Equity curve:

\[
E_t=E_0\prod_{\tau=1}^{t}(1+r_\tau)
\]

Running peak:

\[
H_t=\max_{\tau\leq t} E_\tau
\]

Drawdown:

\[
DD_t=\frac{E_t}{H_t}-1
\]

Maximum drawdown:

\[
\text{MDD}=\min_t DD_t
\]

### Calmar ratio

\[
\text{Calmar}
=
\frac{\text{CAGR}}{|\text{MDD}|}
\]

### Beta and CAPM alpha

\[
\beta_i
=
\frac{\operatorname{Cov}(R_i,R_m)}
{\operatorname{Var}(R_m)}
\]

\[
E[R_i]
=
R_f+\beta_i(E[R_m]-R_f)
\]

Regression alpha:

\[
R_{i,t}-R_{f,t}
=
\alpha_i
+
\beta_i(R_{m,t}-R_{f,t})
+
\epsilon_t
\]

### Value at Risk

For a normally distributed return approximation, one-period parametric VaR in dollar terms:

\[
\operatorname{VaR}_{\alpha}
=
z_\alpha\sigma_P V
\]

For horizon \(h\), under square-root-of-time scaling:

\[
\operatorname{VaR}_{\alpha,h}
\approx
z_\alpha\sigma_P\sqrt{h}\,V
\]

where \(V\) is portfolio value. The \(\sqrt{h}\) rule is an approximation, not a law—especially unreliable during autocorrelation, illiquidity, jumps, or volatility regimes.

### Historical VaR

\[
\operatorname{VaR}_{\alpha}
=
-\operatorname{Quantile}_{1-\alpha}(R_p)\times V
\]

### Expected shortfall / CVaR

\[
\operatorname{ES}_{\alpha}
=
E[L\mid L>\operatorname{VaR}_{\alpha}]
\]

Expected shortfall measures the average loss in the tail beyond VaR. [linkedin](https://www.linkedin.com/posts/riskhuborg_quantfinance-financialengineering-mathematics-activity-7484810240744439808-IqRE)

### Conditional drawdown at risk

\[
\operatorname{CDaR}_{\alpha}
=
E[DD\mid DD\leq \operatorname{DaR}_{\alpha}]
\]

Useful when drawdown—not daily return—is the actual risk constraint.

## Trading Costs, Execution, and Market Microstructure

A backtest without realistic costs is generally not informative.

### Net strategy return

\[
R_{t}^{\text{net}}
=
R_t^{\text{gross}}
-
\text{fees}_t
-
\text{spread cost}_t
-
\text{impact}_t
-
\text{borrow}_t
-
\text{funding}_t
\]

### Turnover

One common definition:

\[
\text{Turnover}_t
=
\frac{1}{2}
\sum_i
|w_{i,t}-w_{i,t-1}|
\]

The factor \(1/2\) avoids double-counting buys and sells in a fully invested portfolio.

### Bid–ask spread and midprice

\[
M_t=\frac{\text{Bid}_t+\text{Ask}_t}{2}
\]

Quoted spread:

\[
S_t^{\text{quoted}}
=
\text{Ask}_t-\text{Bid}_t
\]

Relative spread:

\[
S_t^{\text{relative}}
=
\frac{\text{Ask}_t-\text{Bid}_t}{M_t}
\]

A simple half-spread estimate for crossing the market:

\[
\text{Spread Cost}
\approx
\frac{\text{Ask}-\text{Bid}}{2}
\]

### VWAP

\[
\operatorname{VWAP}
=
\frac{\sum_t P_tV_t}{\sum_tV_t}
\]

where \(V_t\) is traded volume.

### TWAP

\[
\operatorname{TWAP}
=
\frac{1}{n}\sum_{t=1}^{n}P_t
\]

### Implementation shortfall

For a buy order:

\[
\text{IS}
=
\frac{\text{Average Execution Price}-\text{Decision Price}}
{\text{Decision Price}}
\]

For sells, reverse the direction so positive values consistently represent a cost.

### Square-root market impact model

\[
\frac{\text{Impact}}{P}
\approx
Y\sigma
\sqrt{\frac{Q}{V}}
\]

where:

- \(Q\) = shares/units traded,
- \(V\) = typical daily volume,
- \(\sigma\) = daily volatility,
- \(Y\) = calibration coefficient.

### Order-book imbalance

\[
\text{OBI}
=
\frac{V_{\text{bid}}-V_{\text{ask}}}
{V_{\text{bid}}+V_{\text{ask}}}
\]

### Microprice

\[
\text{Microprice}
=
\frac{
\text{Ask}\cdot V_{\text{bid}}
+
\text{Bid}\cdot V_{\text{ask}}
}{
V_{\text{bid}}+V_{\text{ask}}
}
\]

High-frequency market makers may use this, queue position, fill probabilities, short-horizon alpha, inventory, and adverse-selection estimates rather than simple daily-bar indicators.

## Options and Volatility

### Put-call parity

For European options with no dividends:

\[
C-P=S_0-Ke^{-rT}
\]

With continuous dividend yield \(q\):

\[
C-P=S_0e^{-qT}-Ke^{-rT}
\]

### Black–Scholes–Merton

Call:

\[
C
=
S_0e^{-qT}N(d_1)
-
Ke^{-rT}N(d_2)
\]

Put:

\[
P
=
Ke^{-rT}N(-d_2)
-
S_0e^{-qT}N(-d_1)
\]

\[
d_1
=
\frac{
\ln(S_0/K)
+
(r-q+\frac{1}{2}\sigma^2)T
}{
\sigma\sqrt{T}
}
\]

\[
d_2=d_1-\sigma\sqrt{T}
\]

The familiar Black–Scholes call/put formulas, together with the definitions of \(d_1\) and \(d_2\), are standard option-pricing foundations. [linkedin](https://www.linkedin.com/posts/riskhuborg_quantfinance-financialengineering-mathematics-activity-7484810240744439808-IqRE)

### Black–Scholes Greeks

Delta:

\[
\Delta_{\text{call}}
=
e^{-qT}N(d_1)
\]

\[
\Delta_{\text{put}}
=
-e^{-qT}N(-d_1)
\]

Gamma:

\[
\Gamma
=
\frac{
e^{-qT}\phi(d_1)
}{
S_0\sigma\sqrt T
}
\]

Vega:

\[
\nu
=
S_0e^{-qT}\phi(d_1)\sqrt T
\]

Theta for a call:

\[
\Theta_c
=
-\frac{S_0e^{-qT}\phi(d_1)\sigma}{2\sqrt T}
-rKe^{-rT}N(d_2)
+qS_0e^{-qT}N(d_1)
\]

Rho for a call:

\[
\rho_c
=
KTe^{-rT}N(d_2)
\]

Here, \(\phi(\cdot)\) is the standard normal density. In a derivatives book, aggregate exposures are often:

\[
\Delta_{\text{book}}=\sum_i q_i\Delta_i
\]

\[
\Gamma_{\text{book}}=\sum_i q_i\Gamma_i
\]

\[
\text{Vega}_{\text{book}}=\sum_i q_i\nu_i
\]

### Implied volatility

Implied volatility has no closed-form inversion under Black–Scholes. Solve numerically:

\[
\sigma_{\text{IV}}
=
\arg\min_{\sigma>0}
\left(
C_{\text{BS}}(\sigma)-C_{\text{market}}
\right)^2
\]

Newton–Raphson iteration:

\[
\sigma_{n+1}
=
\sigma_n
-
\frac{
C_{\text{BS}}(\sigma_n)-C_{\text{market}}
}{
\operatorname{Vega}(\sigma_n)
}
\]

### Realized volatility

With intraday log returns \(r_i\):

\[
\sigma_{\text{realized},d}
=
\sqrt{\sum_{i=1}^{M}r_i^2}
\]

Annualized:

\[
\sigma_{\text{realized,ann}}
=
\sqrt{252\sum_{i=1}^{M}r_i^2}
\]

A common implementation of realized volatility is the standard deviation of log returns annualized by the square root of observation frequency. [streetofwalls](https://www.streetofwalls.com/finance-training-courses/quantitative-hedge-fund-training/important-quant-math-topics/)

### Variance risk premium

A simple conceptual estimate:

\[
\text{VRP}
=
\sigma_{\text{implied}}^2
-
E[\sigma_{\text{realized}}^2]
\]

Options strategies often care more about *implied variance versus future realized variance* than merely whether an underlying will rise or fall.

## Fixed Income and Macro

### Bond pricing

\[
P
=
\sum_{t=1}^{T}
\frac{CF_t}{(1+y)^t}
\]

Under continuous compounding:

\[
P
=
\sum_{t=1}^{T}
CF_t e^{-y t}
\]

### Zero-coupon discount factor

\[
D(0,T)=e^{-y(0,T)T}
\]

\[
P(0,T)=D(0,T)
\]

### Forward rate

\[
f(0;t_1,t_2)
=
\frac{
\ln D(0,t_1)-\ln D(0,t_2)
}{
t_2-t_1
}
\]

### Macaulay duration

\[
D_{\text{Mac}}
=
\frac{
\sum_t t\cdot PV(CF_t)
}{P}
\]

### Modified duration

\[
D_{\text{mod}}
=
\frac{D_{\text{Mac}}}{1+y}
\]

Small yield-move approximation:

\[
\frac{\Delta P}{P}
\approx
-D_{\text{mod}}\Delta y
\]

### Convexity

\[
\frac{\Delta P}{P}
\approx
-D_{\text{mod}}\Delta y
+
\frac{1}{2}\text{Convexity}(\Delta y)^2
\]

Bond price, duration, and convexity are standard fixed-income calculations. [linkedin](https://www.linkedin.com/posts/riskhuborg_quantfinance-financialengineering-mathematics-activity-7484810240744439808-IqRE)

### FX forward

With domestic rate \(r_d\) and foreign rate \(r_f\):

\[
F_{0,T}
=
S_0 e^{(r_d-r_f)T}
\]

### Futures fair value

For an equity index with dividend yield \(q\):

\[
F_{0,T}=S_0e^{(r-q)T}
\]

For commodities, including storage cost \(u\) and convenience yield \(y\):

\[
F_{0,T}=S_0e^{(r+u-y)T}
\]

## Machine Learning and Model Evaluation

### Logistic regression

Probability of positive class:

\[
p(y=1\mid x)
=
\frac{1}{1+e^{-\beta^\top x}}
\]

Log-odds:

\[
\ln\left(\frac{p}{1-p}\right)
=
\beta^\top x
\]

### Cross-entropy loss

\[
\mathcal{L}
=
-\frac{1}{n}
\sum_{i=1}^{n}
\left[
y_i\ln(\hat p_i)
+
(1-y_i)\ln(1-\hat p_i)
\right]
\]

### Mean squared error

\[
\operatorname{MSE}
=
\frac{1}{n}
\sum_{i=1}^{n}
(y_i-\hat y_i)^2
\]

### Gradient descent

\[
\theta_{k+1}
=
\theta_k
-
\eta\nabla_\theta\mathcal{L}(\theta_k)
\]

### Feature standardization

\[
x^{\text{scaled}}_{i,t}
=
\frac{x_{i,t}-\mu_i}{\sigma_i}
\]

For finance, calculate \(\mu_i\) and \(\sigma_i\) **only from data available at that moment**. Using full-sample information causes look-ahead leakage.

### Rank information coefficient

Cross-sectional rank IC:

\[
IC_t
=
\operatorname{SpearmanCorr}
(\text{signal}_{i,t},r_{i,t+1})
\]

Mean IC:

\[
\overline{IC}
=
\frac{1}{T}\sum_{t=1}^{T}IC_t
\]

IC information ratio:

\[
IR_{IC}
=
\frac{\overline{IC}}
{\operatorname{Std}(IC_t)}
\]

### t-statistic for an estimated mean

\[
t
=
\frac{\bar r}{s/\sqrt n}
\]

But daily financial returns often violate the independent-and-identically-distributed assumption. For autocorrelated returns, use heteroskedasticity/autocorrelation-consistent standard errors or block bootstrap methods.

### Deflated Sharpe ratio concept

If you tested thousands of variants, the best backtest Sharpe is biased upward. A robust research process adjusts for multiple testing, selection bias, non-normal returns, autocorrelation, and the number of trials—rather than treating the raw best Sharpe as proof.

## Backtesting Formulas That Matter Most

The difference between “a formula” and “a deployable quant strategy” is usually here.

### Strategy P&L

For a one-asset position held through return \(r_{t+1}\):

\[
\text{PnL}_{t+1}
=
q_t(P_{t+1}-P_t)
\]

Portfolio P&L:

\[
\text{PnL}_{t+1}
=
V_t w_t^\top r_{t+1}
-
\text{Costs}_{t+1}
\]

Net return:

\[
R_{t+1}^{\text{net}}
=
\frac{\text{PnL}_{t+1}}{V_t}
\]

### Avoiding look-ahead bias

The position must be based on information available before the return it earns:

\[
w_t=f(\mathcal{I}_t)
\]

\[
R_{t+1}=w_t^\top r_{t+1}
\]

not:

\[
R_t=w_t^\top r_t
\]

when \(w_t\) itself was computed from end-of-day \(t\) information.

### Capacity estimate

A rough capacity check compares intended trading volume with market volume:

\[
\text{Participation Rate}
=
\frac{|Q_t|}{ADV_t}
\]

where \(ADV\) is average daily volume. A signal may be attractive at \$100,000 but unusable at \$100 million once spread, impact, borrow availability, and fill quality are included.

### Break-even alpha

Very roughly:

\[
\text{Required Gross Return}
>
\text{Fees}
+
\text{Spread}
+
\text{Impact}
+
\text{Borrow}
+
\text{Funding}
+
\text{Slippage}
\]

For a turnover-based approximation:

\[
\text{Annual Cost}
\approx
\text{Annual Turnover}
\times
\text{One-Way Cost}
\]

## A Minimal Practical Stack

If your goal is to start building actual quant strategies in Python rather than study every branch of quantitative finance, prioritize these calculations first:

1. Log/simple returns, compounding, annualized volatility, and drawdowns.
2. Rolling means, z-scores, EWMA volatility, and cross-sectional rankings.
3. Regression, residuals, autocorrelation, stationarity, and cointegration.
4. Portfolio variance \(w^\top\Sigma w\), inverse-volatility sizing, beta neutrality, and exposure limits.
5. Sharpe, Sortino, maximum drawdown, turnover, VaR/expected shortfall, and rolling out-of-sample results.
6. Bid-ask costs, slippage, market impact, borrow fees, and realistic execution delay.
7. Walk-forward validation, purged time-series cross-validation, and strict anti-leakage data handling.
8. For options: Black–Scholes, implied volatility, Greeks, realized volatility, and volatility-surface dynamics.

## Important Caveat

Most failed retail quant systems do not fail because they lack a more advanced equation. They fail because of:

- Look-ahead bias or survivorship bias.
- Overfitting many features and parameter combinations.
- Ignored transaction costs, latency, and slippage.
- Regime change and unstable correlations.
- Underestimated tail risk and leverage.
- Using price signals without a credible economic or market-microstructure rationale.
- Confusing a statistically significant backtest with a tradable, scalable edge.
