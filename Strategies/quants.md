No finite “exhaustive” list exists: quantitative finance spans trading, portfolio construction, derivatives, risk, execution, fixed income, credit, and machine learning, with firms using proprietary variants. But below is a broad practical formula map—the core calculations a quant researcher, trader, risk quant, or pricing quant is likely to encounter.

Quantitative finance applies mathematical and statistical methods to financial-market and investment-management problems.  In practice, formulas are building blocks: models differ mainly in assumptions, data treatment, constraints, and estimation methods. [en.wikipedia](https://en.wikipedia.org/wiki/Quantitative_analysis_(finance))

## Notation

| Symbol | Meaning |
|---|---|
| \(P_t, S_t\) | Price or spot price at time \(t\) |
| \(r_t\) | Simple return |
| \(R_t\) | Log return |
| \(r_f\) | Risk-free rate |
| \(\mu\) | Expected return / drift |
| \(\sigma\) | Volatility / standard deviation |
| \(\Sigma\) | Covariance matrix |
| \(w\) | Portfolio-weight vector |
| \(T\) | Time to maturity, usually in years |
| \(K\) | Option strike price |
| \(N(\cdot)\) | Standard-normal CDF |
| \(\phi(\cdot)\) | Standard-normal PDF |
| \(q\) | Continuous dividend yield |
| \(\lambda\) | Hazard/default intensity |
| \(N\) | Notional, observations, or simulations depending on context |

## Market Data and Returns

### Price transformations

- **Simple return**
  \[
  r_t=\frac{P_t-P_{t-1}}{P_{t-1}}=\frac{P_t}{P_{t-1}}-1
  \]

- **Gross return**
  \[
  G_t=1+r_t=\frac{P_t}{P_{t-1}}
  \]

- **Log return**
  \[
  R_t=\ln\left(\frac{P_t}{P_{t-1}}\right)
  \]

- **Cumulative simple return**
  \[
  R_{0,T}=\prod_{t=1}^{T}(1+r_t)-1
  \]

- **Cumulative log return**
  \[
  R_{0,T}=\sum_{t=1}^{T}\ln\left(\frac{P_t}{P_{t-1}}\right)
  =\ln\left(\frac{P_T}{P_0}\right)
  \]

- **Annualized return from periodic compounded returns**
  \[
  R_{\text{ann}}=\left(\prod_{t=1}^{n}(1+r_t)\right)^{m/n}-1
  \]
  where \(m\) is the number of periods per year.

- **Compound annual growth rate**
  \[
  \operatorname{CAGR}=\left(\frac{V_T}{V_0}\right)^{1/T}-1
  \]

- **Excess return**
  \[
  r_t^{e}=r_t-r_{f,t}
  \]

- **Real return approximation**
  \[
  r_{\text{real}}\approx r_{\text{nominal}}-\pi
  \]
  where \(\pi\) is inflation. Exact form:
  \[
  1+r_{\text{real}}=\frac{1+r_{\text{nominal}}}{1+\pi}
  \]

### Corporate-action adjustments

- **Total-return price update**
  \[
  P_t^{TR}=P_{t-1}^{TR}\left(\frac{P_t+D_t}{P_{t-1}}\right)
  \]
  where \(D_t\) is cash dividend per share.

- **Market capitalization**
  \[
  \text{Market Cap}=P_t\times \text{Shares Outstanding}
  \]

- **Enterprise value**
  \[
  EV=\text{Equity Value}+\text{Debt}+\text{Preferred Equity}+\text{Minority Interest}-\text{Cash}
  \]

## Statistics and Estimation

### Descriptive statistics

- **Sample mean**
  \[
  \bar{x}=\frac{1}{n}\sum_{i=1}^{n}x_i
  \]

- **Weighted mean**
  \[
  \bar{x}_w=\frac{\sum_i w_i x_i}{\sum_i w_i}
  \]

- **Sample variance**
  \[
  s^2=\frac{1}{n-1}\sum_{i=1}^{n}(x_i-\bar{x})^2
  \]

- **Population variance**
  \[
  \sigma^2=\frac{1}{n}\sum_{i=1}^{n}(x_i-\mu)^2
  \]

- **Standard deviation**
  \[
  \sigma=\sqrt{\operatorname{Var}(X)}
  \]

- **Annualized volatility**
  \[
  \sigma_{\text{ann}}=\sigma_{\text{period}}\sqrt{m}
  \]
  This square-root-of-time scaling is standard under independent, identically distributed returns; realized volatility is commonly the standard deviation of log returns multiplied by the square root of data frequency. [streetofwalls](https://www.streetofwalls.com/finance-training-courses/quantitative-hedge-fund-training/important-quant-math-topics/)

- **Covariance**
  \[
  \operatorname{Cov}(X,Y)=\frac{1}{n-1}\sum_{i=1}^{n}(x_i-\bar{x})(y_i-\bar{y})
  \]

- **Correlation**
  \[
  \rho_{X,Y}=
  \frac{\operatorname{Cov}(X,Y)}
  {\sigma_X\sigma_Y}
  \]
  Correlation ranges from \(-1\) to \(+1\). [streetofwalls](https://www.streetofwalls.com/finance-training-courses/quantitative-hedge-fund-training/important-quant-math-topics/)

- **Skewness**
  \[
  \operatorname{Skew}(X)=
  \frac{E[(X-\mu)^3]}{\sigma^3}
  \]

- **Excess kurtosis**
  \[
  \operatorname{ExcessKurt}(X)=
  \frac{E[(X-\mu)^4]}{\sigma^4}-3
  \]

- **Quantile**
  \[
  Q_\alpha=\inf\{x:F_X(x)\ge \alpha\}
  \]

- **Z-score**
  \[
  z_i=\frac{x_i-\mu}{\sigma}
  \]

- **Median absolute deviation**
  \[
  \operatorname{MAD}=\operatorname{median}\left(|x_i-\operatorname{median}(x)|\right)
  \]

### Moving and exponentially weighted statistics

- **Simple moving average**
  \[
  SMA_t^{(L)}=\frac{1}{L}\sum_{i=0}^{L-1}P_{t-i}
  \]

- **Exponentially weighted moving average**
  \[
  EMA_t=\alpha P_t+(1-\alpha)EMA_{t-1}
  \]

- **EWMA variance**
  \[
  \sigma_t^2=\lambda\sigma_{t-1}^2+(1-\lambda)r_{t-1}^2
  \]

- **EWMA covariance**
  \[
  \Sigma_t=\lambda\Sigma_{t-1}+(1-\lambda)r_{t-1}r_{t-1}^{\top}
  \]

- **Rolling volatility**
  \[
  \hat{\sigma}_{t,L}=
  \sqrt{\frac{1}{L-1}
  \sum_{i=0}^{L-1}(r_{t-i}-\bar r_{t,L})^2}
  \]

### Regression and inference

- **Ordinary least squares**
  \[
  \hat{\beta}=(X^\top X)^{-1}X^\top y
  \]

- **Linear regression**
  \[
  y=X\beta+\varepsilon
  \]

- **Residual**
  \[
  \hat{\varepsilon}=y-X\hat{\beta}
  \]

- **Residual sum of squares**
  \[
  RSS=\sum_{i=1}^{n}(y_i-\hat y_i)^2
  \]

- **Coefficient of determination**
  \[
  R^2=1-\frac{RSS}{TSS}
  \]
  where
  \[
  TSS=\sum_{i=1}^{n}(y_i-\bar y)^2
  \]
  \(R^2\) measures the share of variation explained by a chosen model. [streetofwalls](https://www.streetofwalls.com/finance-training-courses/quantitative-hedge-fund-training/important-quant-math-topics/)

- **Adjusted \(R^2\)**
  \[
  \bar R^2=1-(1-R^2)\frac{n-1}{n-k-1}
  \]

- **Standard error of a coefficient**
  \[
  SE(\hat{\beta}_j)=
  \sqrt{\hat{\sigma}_{\varepsilon}^{2}
  \left[(X^\top X)^{-1}\right]_{jj}}
  \]

- **t-statistic**
  \[
  t=\frac{\hat{\beta}_j-\beta_{j,0}}{SE(\hat{\beta}_j)}
  \]

- **Information criteria**
  \[
  AIC=2k-2\ln(\hat L)
  \]
  \[
  BIC=k\ln(n)-2\ln(\hat L)
  \]

- **Maximum-likelihood estimation**
  \[
  \hat{\theta}_{MLE}=\arg\max_\theta \prod_{i=1}^{n}f(x_i\mid\theta)
  \]
  Equivalently,
  \[
  \hat{\theta}_{MLE}=\arg\max_\theta \sum_{i=1}^{n}\ln f(x_i\mid\theta)
  \]

### Time-series diagnostics

- **Autocorrelation at lag \(k\)**
  \[
  \rho_k=
  \frac{\operatorname{Cov}(r_t,r_{t-k})}
  {\operatorname{Var}(r_t)}
  \]

- **AR(\(p\)) model**
  \[
  r_t=c+\sum_{i=1}^{p}\phi_i r_{t-i}+\varepsilon_t
  \]

- **MA(\(q\)) model**
  \[
  r_t=\mu+\varepsilon_t+\sum_{i=1}^{q}\theta_i\varepsilon_{t-i}
  \]

- **ARMA(\(p,q\))**
  \[
  r_t=c+\sum_{i=1}^{p}\phi_i r_{t-i}
  +\varepsilon_t+\sum_{j=1}^{q}\theta_j\varepsilon_{t-j}
  \]

- **ARIMA(\(p,d,q\))**
  \[
  \phi(B)(1-B)^d r_t=c+\theta(B)\varepsilon_t
  \]

- **Augmented Dickey–Fuller regression**
  \[
  \Delta y_t=\alpha+\beta t+\gamma y_{t-1}
  +\sum_{i=1}^{p}\delta_i\Delta y_{t-i}+\varepsilon_t
  \]

- **Cointegrating spread**
  \[
  z_t=y_t-\beta x_t
  \]

- **Ornstein–Uhlenbeck mean-reverting process**
  \[
  dX_t=\kappa(\theta-X_t)dt+\sigma dW_t
  \]

## Volatility Models

### Historical and range-based volatility

- **Close-to-close realized variance**
  \[
  RV_t=\sum_{i=1}^{n}r_{t,i}^{2}
  \]

- **Realized volatility**
  \[
  \sigma_{RV}=\sqrt{\sum_{i=1}^{n}r_{t,i}^{2}}
  \]

- **Parkinson volatility estimator**
  \[
  \hat{\sigma}_{P}^{2}
  =\frac{1}{4n\ln 2}
  \sum_{t=1}^{n}
  \left[\ln\left(\frac{H_t}{L_t}\right)\right]^2
  \]

- **Garman–Klass estimator**
  \[
  \hat{\sigma}_{GK}^{2}=
  \frac{1}{n}\sum_{t=1}^{n}
  \left[
  \frac{1}{2}\ln^2\left(\frac{H_t}{L_t}\right)
  -(2\ln 2-1)\ln^2\left(\frac{C_t}{O_t}\right)
  \right]
  \]

### ARCH/GARCH family

- **ARCH(\(q\))**
  \[
  \sigma_t^2=\omega+\sum_{i=1}^{q}\alpha_i\varepsilon_{t-i}^{2}
  \]

- **GARCH(\(p,q\))**
  \[
  \sigma_t^2=\omega+
  \sum_{i=1}^{q}\alpha_i\varepsilon_{t-i}^{2}
  +\sum_{j=1}^{p}\beta_j\sigma_{t-j}^{2}
  \]

- **GARCH(1,1)**
  \[
  \sigma_t^2=\omega+\alpha\varepsilon_{t-1}^{2}
  +\beta\sigma_{t-1}^{2}
  \]

- **Long-run GARCH variance**
  \[
  \operatorname{Var}_{\infty}=
  \frac{\omega}{1-\alpha-\beta}
  \]

- **GJR-GARCH**
  \[
  \sigma_t^2=\omega+\alpha\varepsilon_{t-1}^2+
  \gamma I_{\{\varepsilon_{t-1}<0\}}\varepsilon_{t-1}^2+
  \beta\sigma_{t-1}^2
  \]

- **EGARCH**
  \[
  \ln(\sigma_t^2)=\omega+\beta\ln(\sigma_{t-1}^2)
  +\alpha\left|\frac{\varepsilon_{t-1}}{\sigma_{t-1}}\right|
  +\gamma\frac{\varepsilon_{t-1}}{\sigma_{t-1}}
  \]

## Portfolio Construction

### Portfolio moments

- **Portfolio return**
  \[
  R_p=w^\top R=\sum_{i=1}^{n}w_iR_i
  \]

- **Expected portfolio return**
  \[
  E[R_p]=w^\top\mu
  \]

- **Portfolio variance**
  \[
  \sigma_p^2=w^\top\Sigma w
  \]

- **Portfolio volatility**
  \[
  \sigma_p=\sqrt{w^\top\Sigma w}
  \]

- **Two-asset variance**
  \[
  \sigma_p^2=
  w_1^2\sigma_1^2+w_2^2\sigma_2^2+
  2w_1w_2\rho_{12}\sigma_1\sigma_2
  \]

- **Marginal contribution to risk**
  \[
  MCR_i=\frac{(\Sigma w)_i}{\sigma_p}
  \]

- **Component contribution to risk**
  \[
  CCR_i=w_i\frac{(\Sigma w)_i}{\sigma_p}
  \]

- **Percentage contribution to risk**
  \[
  PCR_i=\frac{CCR_i}{\sigma_p}
  \]

### Mean-variance optimization

- **Global minimum-variance portfolio**
  \[
  \min_w w^\top\Sigma w
  \quad\text{subject to}\quad
  \mathbf{1}^\top w=1
  \]

- **Unconstrained GMV weights**
  \[
  w_{GMV}=
  \frac{\Sigma^{-1}\mathbf{1}}
  {\mathbf{1}^\top\Sigma^{-1}\mathbf{1}}
  \]

- **Maximum-Sharpe portfolio**
  \[
  \max_w
  \frac{w^\top(\mu-r_f\mathbf{1})}
  {\sqrt{w^\top\Sigma w}}
  \]

- **Tangency-portfolio weights**
  \[
  w_T=
  \frac{\Sigma^{-1}(\mu-r_f\mathbf{1})}
  {\mathbf{1}^{\top}\Sigma^{-1}(\mu-r_f\mathbf{1})}
  \]

- **Markowitz target-return program**
  \[
  \min_w w^\top\Sigma w
  \]
  subject to
  \[
  w^\top\mu=\mu^*,\qquad
  \mathbf{1}^\top w=1
  \]

- **Utility-maximizing portfolio**
  \[
  \max_w\left(w^\top\mu-\frac{\gamma}{2}w^\top\Sigma w\right)
  \]

- **Transaction-cost-aware optimization**
  \[
  \max_w
  \left[
  w^\top\mu-\frac{\gamma}{2}w^\top\Sigma w
  -\lambda\sum_i|w_i-w_{i,\text{old}}|
  \right]
  \]

### Alternative allocation methods

- **Equal weight**
  \[
  w_i=\frac{1}{N}
  \]

- **Inverse-volatility weight**
  \[
  w_i=\frac{1/\sigma_i}{\sum_{j=1}^{N}1/\sigma_j}
  \]

- **Risk parity condition**
  \[
  w_i(\Sigma w)_i=w_j(\Sigma w)_j
  \quad\forall i,j
  \]

- **Minimum variance**
  \[
  \min_w w^\top\Sigma w
  \]

- **Maximum diversification ratio**
  \[
  \max_w
  \frac{\sum_iw_i\sigma_i}
  {\sqrt{w^\top\Sigma w}}
  \]

- **Black–Litterman posterior expected returns**
  \[
  \mu_{BL}=
  \left[(\tau\Sigma)^{-1}+P^\top\Omega^{-1}P\right]^{-1}
  \left[(\tau\Sigma)^{-1}\pi+P^\top\Omega^{-1}Q\right]
  \]

- **Market-implied equilibrium returns**
  \[
  \pi=\delta\Sigma w_{\text{mkt}}
  \]

- **Kelly fraction, single asset**
  \[
  f^*=\frac{bp-q}{b}
  \]
  where \(b\) is net odds, \(p\) probability of winning, and \(q=1-p\).

- **Kelly portfolio approximation**
  \[
  w^*\approx\Sigma^{-1}\mu
  \]

## Factor Models and Asset Pricing

### CAPM and beta

- **CAPM**
  \[
  E[R_i]=r_f+\beta_i(E[R_m]-r_f)
  \]
  CAPM connects expected return to systematic market risk. [linkedin](https://www.linkedin.com/posts/prateek964_quantfinance-mathematics-finance-activity-7478466524215697411-8bYk)

- **Beta**
  \[
  \beta_i=
  \frac{\operatorname{Cov}(R_i,R_m)}
  {\operatorname{Var}(R_m)}
  \]

- **Jensen’s alpha**
  \[
  \alpha_i=
  R_i-\left[r_f+\beta_i(R_m-r_f)\right]
  \]

- **Security Market Line**
  \[
  E[R_i]-r_f=\beta_i(E[R_m]-r_f)
  \]

### Multifactor models

- **Generic factor model**
  \[
  R_{i,t}=\alpha_i+\beta_i^\top f_t+\varepsilon_{i,t}
  \]

- **Fama–French three-factor model**
  \[
  R_i-r_f=
  \alpha+\beta_M(MKT-r_f)+
  \beta_S SMB+\beta_H HML+\varepsilon
  \]

- **Fama–French five-factor model**
  \[
  R_i-r_f=
  \alpha+\beta_M MKT+
  \beta_S SMB+
  \beta_H HML+
  \beta_R RMW+
  \beta_C CMA+\varepsilon
  \]

- **Carhart four-factor model**
  \[
  R_i-r_f=
  \alpha+\beta_M MKT+\beta_S SMB+
  \beta_H HML+\beta_U UMD+\varepsilon
  \]

- **Factor covariance model**
  \[
  \Sigma=BFB^\top+D
  \]
  where \(B\) is exposure matrix, \(F\) factor covariance, and \(D\) idiosyncratic covariance.

- **Information coefficient**
  \[
  IC=\operatorname{Corr}(\text{forecast},\text{realized return})
  \]

- **Information ratio**
  \[
  IR=\frac{R_p-R_b}{\sigma(R_p-R_b)}
  \]

- **Fundamental law of active management**
  \[
  IR\approx IC\sqrt{BR}
  \]
  where \(BR\) is breadth, often approximated as independent investment decisions.

## Risk and Performance

### Risk-adjusted performance

- **Sharpe ratio**
  \[
  \operatorname{Sharpe}=
  \frac{E[R_p-r_f]}{\sigma(R_p-r_f)}
  \]

- **Annualized Sharpe ratio**
  \[
  \operatorname{Sharpe}_{\text{ann}}
  \approx \operatorname{Sharpe}_{\text{period}}\sqrt{m}
  \]

- **Sortino ratio**
  \[
  \operatorname{Sortino}=
  \frac{E[R_p-r_f]}{\sigma_{\text{downside}}}
  \]

- **Downside deviation**
  \[
  \sigma_{\text{downside}}=
  \sqrt{\frac{1}{n}
  \sum_{t=1}^{n}
  \min(R_t-TAR,0)^2}
  \]

- **Treynor ratio**
  \[
  \operatorname{Treynor}=
  \frac{R_p-r_f}{\beta_p}
  \]

- **Calmar ratio**
  \[
  \operatorname{Calmar}=
  \frac{\operatorname{CAGR}}{|\operatorname{MaxDrawdown}|}
  \]

- **Omega ratio**
  \[
  \Omega(\tau)=
  \frac{\int_{\tau}^{\infty}[1-F(r)]dr}
  {\int_{-\infty}^{\tau}F(r)dr}
  \]

### Drawdowns

- **Running peak**
  \[
  M_t=\max_{u\le t}V_u
  \]

- **Drawdown**
  \[
  DD_t=\frac{V_t}{M_t}-1
  \]

- **Maximum drawdown**
  \[
  MDD=\min_t DD_t
  \]

- **Ulcer index**
  \[
  UI=\sqrt{\frac{1}{n}\sum_{t=1}^{n}DD_t^2}
  \]

### Value at Risk and expected shortfall

- **Historical VaR**
  \[
  VaR_{\alpha}=-Q_{\alpha}(R)
  \]

- **Parametric normal VaR**
  \[
  VaR_{\alpha}=z_\alpha\sigma_p\sqrt{h}
  \]
  or, including mean:
  \[
  VaR_\alpha=
  -\left(\mu_ph+z_\alpha\sigma_p\sqrt h\right)
  \]

- **Dollar VaR**
  \[
  VaR_{\$}=V_0\times VaR_{\alpha}
  \]

- **Expected shortfall / conditional VaR**
  \[
  ES_{\alpha}=
  -E[R\mid R\le -VaR_\alpha]
  \]

- **Normal-distribution expected shortfall**
  \[
  ES_\alpha=
  \sigma\frac{\phi(z_\alpha)}{1-\alpha}
  -\mu
  \]

- **Incremental VaR**
  \[
  IVaR_i=VaR(w+\Delta w_i)-VaR(w)
  \]

- **Component VaR**
  \[
  CVaR_i=w_i\frac{\partial VaR}{\partial w_i}
  \]

### Stress testing

- **Scenario P&L**
  \[
  \Delta V\approx
  \sum_i\frac{\partial V}{\partial x_i}\Delta x_i+
  \frac{1}{2}\sum_{i,j}
  \frac{\partial^2V}{\partial x_i\partial x_j}
  \Delta x_i\Delta x_j
  \]

- **Factor stress P&L**
  \[
  \Delta V\approx \beta^\top \Delta f
  \]

## Options and Derivatives

### No-arbitrage and payoffs

- **Forward price, no income**
  \[
  F_{0,T}=S_0e^{rT}
  \]

- **Forward price with continuous dividend yield**
  \[
  F_{0,T}=S_0e^{(r-q)T}
  \]

- **Forward price with discrete income**
  \[
  F_{0,T}=(S_0-PV(\text{income}))e^{rT}
  \]

- **Long forward payoff at expiry**
  \[
  \Pi_T=S_T-K
  \]

- **Call payoff**
  \[
  C_T=\max(S_T-K,0)
  \]

- **Put payoff**
  \[
  P_T=\max(K-S_T,0)
  \]

- **Put-call parity, European options**
  \[
  C-P=S_0e^{-qT}-Ke^{-rT}
  \]

- **Box spread identity**
  \[
  C(K_1)-C(K_2)+P(K_2)-P(K_1)
  =(K_2-K_1)e^{-rT}
  \]

### Black–Scholes–Merton

- **Call price**
  \[
  C=S_0e^{-qT}N(d_1)-Ke^{-rT}N(d_2)
  \]

- **Put price**
  \[
  P=Ke^{-rT}N(-d_2)-S_0e^{-qT}N(-d_1)
  \]

- **Black–Scholes inputs**
  \[
  d_1=
  \frac{\ln(S_0/K)+(r-q+\frac{1}{2}\sigma^2)T}
  {\sigma\sqrt T}
  \]
  \[
  d_2=d_1-\sigma\sqrt T
  \]

- **Black–Scholes PDE**
  \[
  \frac{\partial V}{\partial t}
  +\frac{1}{2}\sigma^2S^2
  \frac{\partial^2V}{\partial S^2}
  +(r-q)S\frac{\partial V}{\partial S}
  -rV=0
  \]
  The Black–Scholes price and PDE are central European-option pricing formulas. [linkedin](https://www.linkedin.com/posts/prateek964_quantfinance-mathematics-finance-activity-7478466524215697411-8bYk)

### Greeks

- **Delta**
  \[
  \Delta=\frac{\partial V}{\partial S}
  \]

- **Call delta**
  \[
  \Delta_C=e^{-qT}N(d_1)
  \]

- **Put delta**
  \[
  \Delta_P=e^{-qT}[N(d_1)-1]
  \]

- **Gamma**
  \[
  \Gamma=\frac{\partial^2V}{\partial S^2}
  \]

- **Black–Scholes gamma**
  \[
  \Gamma=
  \frac{e^{-qT}\phi(d_1)}
  {S_0\sigma\sqrt T}
  \]

- **Vega**
  \[
  \nu=\frac{\partial V}{\partial \sigma}
  \]
  \[
  \nu=S_0e^{-qT}\phi(d_1)\sqrt T
  \]

- **Theta**
  \[
  \Theta=\frac{\partial V}{\partial t}
  \]

- **Rho**
  \[
  \rho=\frac{\partial V}{\partial r}
  \]

- **Charm**
  \[
  \operatorname{Charm}=\frac{\partial\Delta}{\partial t}
  \]

- **Vanna**
  \[
  \operatorname{Vanna}=
  \frac{\partial^2V}{\partial S\partial\sigma}
  \]

- **Vomma / volga**
  \[
  \operatorname{Vomma}=
  \frac{\partial^2V}{\partial\sigma^2}
  \]

- **Delta-gamma approximation**
  \[
  \Delta V\approx
  \Delta\,\Delta S+
  \frac{1}{2}\Gamma(\Delta S)^2+
  \nu\Delta\sigma+
  \Theta\Delta t
  \]

### Implied volatility and volatility surface

- **Implied volatility**
  \[
  \sigma_{\text{imp}}
  :\quad
  V_{\text{market}}=
  V_{\text{model}}(S,K,r,q,T,\sigma_{\text{imp}})
  \]

- **Moneyness**
  \[
  m=\frac{K}{S_0}
  \]

- **Log moneyness**
  \[
  k=\ln\left(\frac{K}{F_{0,T}}\right)
  \]

- **Variance swap fair strike approximation**
  \[
  K_{\text{var}}\approx
  \frac{2e^{rT}}{T}
  \left[
  \int_0^F\frac{P(K)}{K^2}dK+
  \int_F^\infty\frac{C(K)}{K^2}dK
  \right]
  \]

### Binomial-tree pricing

- **Up/down factors**
  \[
  u=e^{\sigma\sqrt{\Delta t}},
  \qquad
  d=e^{-\sigma\sqrt{\Delta t}}
  \]

- **Risk-neutral probability**
  \[
  p=\frac{e^{(r-q)\Delta t}-d}{u-d}
  \]

- **Backward induction**
  \[
  V_t=e^{-r\Delta t}
  \left[pV_{t+\Delta t}^{u}+
  (1-p)V_{t+\Delta t}^{d}\right]
  \]

- **American option recursion**
  \[
  V_t=\max\left(
  \text{intrinsic value},
  e^{-r\Delta t}
  [pV_u+(1-p)V_d]
  \right)
  \]

### Stochastic processes

- **Geometric Brownian motion**
  \[
  dS_t=\mu S_tdt+\sigma S_tdW_t
  \]

- **GBM terminal distribution**
  \[
  S_T=S_0
  \exp\left[
  \left(\mu-\frac{1}{2}\sigma^2\right)T+
  \sigma\sqrt T Z
  \right]
  \]

- **Risk-neutral GBM**
  \[
  dS_t=(r-q)S_tdt+\sigma S_tdW_t^{\mathbb Q}
  \]

- **Heston stochastic-volatility model**
  \[
  dS_t=\mu S_tdt+\sqrt{v_t}S_tdW_{1,t}
  \]
  \[
  dv_t=\kappa(\theta-v_t)dt+
  \xi\sqrt{v_t}dW_{2,t}
  \]
  \[
  dW_1dW_2=\rho dt
  \]
  This model allows variance itself to evolve stochastically. [linkedin](https://www.linkedin.com/posts/prateek964_quantfinance-mathematics-finance-activity-7478466524215697411-8bYk)

- **Merton jump diffusion**
  \[
  \frac{dS_t}{S_t}
  =(\mu-\lambda k)dt+
  \sigma dW_t+
  (J-1)dN_t
  \]

- **Local-volatility model**
  \[
  dS_t=(r-q)S_tdt+\sigma_{\text{loc}}(S_t,t)S_tdW_t
  \]

- **Dupire local-volatility formula**
  \[
  \sigma_{\text{loc}}^2(K,T)=
  \frac{
  \frac{\partial C}{\partial T}
  +(r-q)K\frac{\partial C}{\partial K}
  +qC
  }{
  \frac{1}{2}K^2\frac{\partial^2C}{\partial K^2}
  }
  \]

## Fixed Income and Rates

### Bond pricing and yield

- **Present value of cash flows**
  \[
  P=\sum_{i=1}^{n}\frac{CF_i}{(1+y/m)^{mt_i}}
  \]

- **Continuous-compounding bond price**
  \[
  P=\sum_{i=1}^{n}CF_i e^{-y t_i}
  \]

- **Zero-coupon bond**
  \[
  P(0,T)=e^{-y(0,T)T}
  \]

- **Continuously compounded zero rate**
  \[
  y(0,T)=-\frac{\ln P(0,T)}{T}
  \]

- **Discount factor**
  \[
  DF(0,T)=e^{-y(0,T)T}
  \]

- **Current yield**
  \[
  \text{Current Yield}=
  \frac{\text{Annual Coupon}}{\text{Bond Market Price}}
  \]

- **Approximate yield to maturity**
  \[
  YTM\approx
  \frac{C+(F-P)/n}
  {(F+P)/2}
  \]
  A common approximation uses annual coupon, par value, market price, and years to maturity. [certfuel](https://www.certfuel.com/series-65/exam-topics/formulas/)

- **Accrued interest**
  \[
  AI=\text{Coupon Payment}
  \times
  \frac{\text{Days Since Last Coupon}}
  {\text{Days in Coupon Period}}
  \]

- **Dirty price**
  \[
  P_{\text{dirty}}=P_{\text{clean}}+AI
  \]

### Duration and convexity

- **Macaulay duration**
  \[
  D_{\text{Mac}}=
  \frac{
  \sum_{i=1}^{n}t_i
  \frac{CF_i}{(1+y/m)^{mt_i}}
  }{P}
  \]

- **Modified duration**
  \[
  D_{\text{mod}}=
  \frac{D_{\text{Mac}}}{1+y/m}
  \]

- **First-order bond-price change**
  \[
  \frac{\Delta P}{P}
  \approx-D_{\text{mod}}\Delta y
  \]

- **Convexity**
  \[
  \operatorname{Convexity}=
  \frac{1}{P}
  \sum_i
  \frac{CF_i\,t_i(t_i+1)}
  {(1+y)^{t_i+2}}
  \]

- **Duration-convexity approximation**
  \[
  \frac{\Delta P}{P}
  \approx
  -D_{\text{mod}}\Delta y+
  \frac{1}{2}\operatorname{Convexity}(\Delta y)^2
  \]

- **DV01 / PV01**
  \[
  DV01\approx
  D_{\text{mod}}P\times0.0001
  \]

### Yield curves and swaps

- **Forward rate from discount factors**
  \[
  F(t_1,t_2)=
  \frac{1}{t_2-t_1}
  \ln\left(
  \frac{P(0,t_1)}{P(0,t_2)}
  \right)
  \]

- **Discrete forward rate**
  \[
  1+F_{t_1,t_2}(t_2-t_1)=
  \frac{P(0,t_1)}{P(0,t_2)}
  \]

- **Par swap rate**
  \[
  S_{\text{swap}}=
  \frac{1-P(0,T_n)}
  {\sum_{i=1}^{n}\alpha_iP(0,T_i)}
  \]

- **Fixed-leg present value**
  \[
  PV_{\text{fixed}}=
  N K\sum_{i=1}^{n}\alpha_iP(0,T_i)
  \]

- **Floating-leg present value at reset**
  \[
  PV_{\text{float}}=
  N[1-P(0,T_n)]
  \]

- **FRA value**
  \[
  V_{\text{FRA}}=
  N\frac{(L-K)\delta}
  {1+L\delta}
  DF
  \]

- **Bond-futures basis**
  \[
  \text{Basis}=
  \text{Cash Bond Price}-
  \text{Futures Price}\times\text{Conversion Factor}
  \]

## Credit and Counterparty Risk

### Credit-spread and default models

- **Credit spread**
  \[
  s=y_{\text{corporate}}-y_{\text{risk-free}}
  \]

- **Hazard-rate survival probability**
  \[
  S(t)=\Pr(\tau>t)=
  \exp\left(-\int_0^t\lambda(u)du\right)
  \]

- **Constant-hazard survival probability**
  \[
  S(t)=e^{-\lambda t}
  \]

- **Default probability by time \(t\)**
  \[
  PD(0,t)=1-S(t)
  \]

- **Approximate credit-spread relation**
  \[
  s\approx\lambda(1-RR)
  \]
  where \(RR\) is recovery rate.

- **Expected loss**
  \[
  EL=PD\times LGD\times EAD
  \]

- **Loss given default**
  \[
  LGD=1-RR
  \]

- **Expected credit loss over time**
  \[
  ECL=\sum_t PD_t\times LGD_t\times EAD_t\times DF_t
  \]

### Structural and counterparty models

- **Merton equity-as-call model**
  \[
  E=V N(d_1)-De^{-rT}N(d_2)
  \]

- **Distance to default**
  \[
  DD=
  \frac{\ln(V/D)+(\mu-\frac12\sigma_V^2)T}
  {\sigma_V\sqrt T}
  \]

- **Expected positive exposure**
  \[
  EPE_t=E[\max(V_t,0)]
  \]

- **Credit valuation adjustment**
  \[
  CVA\approx
  (1-RR)
  \sum_iDF(0,t_i)\,
  EPE_{t_i}\,
  \Delta PD_i
  \]

- **Debit valuation adjustment**
  \[
  DVA\approx
  (1-RR_{\text{own}})
  \sum_iDF(0,t_i)\,
  ENE_{t_i}\,
  \Delta PD_{\text{own},i}
  \]

- **Funding valuation adjustment**
  \[
  FVA\approx
  \sum_iDF(0,t_i)\,
  \text{Funding Spread}_{t_i}
  \times \text{Funding Exposure}_{t_i}
  \]

## Execution and Market Microstructure

### Quotes, spreads, and impact

- **Midprice**
  \[
  m_t=\frac{a_t+b_t}{2}
  \]

- **Quoted bid–ask spread**
  \[
  \text{Spread}=a_t-b_t
  \]

- **Relative spread**
  \[
  \text{Relative Spread}=
  \frac{a_t-b_t}{m_t}
  \]

- **Effective spread**
  \[
  \text{Effective Spread}=
  2D_t\frac{P_t-m_t}{m_t}
  \]
  where \(D_t=+1\) for buyer-initiated and \(-1\) for seller-initiated trades.

- **Realized spread**
  \[
  \text{Realized Spread}=
  2D_t\frac{P_t-m_{t+\Delta}}{m_t}
  \]

- **Order-book imbalance**
  \[
  I=
  \frac{V_{\text{bid}}-V_{\text{ask}}}
  {V_{\text{bid}}+V_{\text{ask}}}
  \]

- **Volume-weighted average price**
  \[
  VWAP=
  \frac{\sum_iP_iV_i}{\sum_iV_i}
  \]

- **Time-weighted average price**
  \[
  TWAP=\frac{1}{n}\sum_{i=1}^{n}P_i
  \]

- **Participation rate**
  \[
  \text{POV}=
  \frac{\text{Your Executed Volume}}
  {\text{Market Volume}}
  \]

- **Implementation shortfall**
  \[
  IS=
  \text{Decision Price Value}-
  \text{Actual Execution Value}+
  \text{Opportunity Cost}
  \]

- **Almgren–Chriss temporary impact**
  \[
  h(v)=\eta v
  \]

- **Almgren–Chriss permanent impact**
  \[
  g(v)=\gamma v
  \]

- **Square-root market-impact law**
  \[
  \frac{\Delta P}{P}
  \approx
  Y\sigma\sqrt{\frac{Q}{V}}
  \]
  where \(Q\) is order size and \(V\) is market volume.

## Statistical Arbitrage and Signals

### Mean reversion

- **Rolling z-score**
  \[
  z_t=
  \frac{x_t-\mu_{t,L}}
  {\sigma_{t,L}}
  \]

- **Pairs-trading spread**
  \[
  s_t=y_t-\beta x_t
  \]

- **Spread z-score**
  \[
  z_t=
  \frac{s_t-\bar{s}_L}
  {\operatorname{std}(s)_L}
  \]

- **Half-life of mean reversion**
  \[
  \text{Half-Life}=
  -\frac{\ln 2}{\ln(1+\hat\phi)}
  \]
  for an estimated AR(1) mean-reversion coefficient \(\hat\phi<0\) in \(\Delta x_t=\phi x_{t-1}+\varepsilon_t\).

- **Ornstein–Uhlenbeck expected value**
  \[
  E[X_t\mid X_0]=
  \theta+(X_0-\theta)e^{-\kappa t}
  \]

### Momentum and trend

- **Price momentum**
  \[
  MOM_{t,L}=\frac{P_t}{P_{t-L}}-1
  \]

- **Rate of change**
  \[
  ROC_{t,L}=
  \frac{P_t-P_{t-L}}{P_{t-L}}\times100
  \]

- **Moving-average crossover**
  \[
  \text{Signal}_t=
  \operatorname{sign}
  \left(SMA_t^{\text{short}}-SMA_t^{\text{long}}\right)
  \]

- **Relative-strength index**
  \[
  RS=\frac{\text{Average Gain}}{\text{Average Loss}}
  \]
  \[
  RSI=100-\frac{100}{1+RS}
  \]

- **MACD**
  \[
  MACD_t=EMA_t^{(12)}-EMA_t^{(26)}
  \]

### Cross-sectional alpha

- **Cross-sectional standardized factor score**
  \[
  z_{i,t}=
  \frac{x_{i,t}-\mu_t(x)}
  {\sigma_t(x)}
  \]

- **Rank signal**
  \[
  \operatorname{Rank}_{i,t}=
  \frac{\operatorname{rank}(x_{i,t})}
  {N_t}
  \]

- **Winsorization**
  \[
  x_i^{W}=
  \min(\max(x_i,Q_l),Q_u)
  \]

- **Neutralized signal**
  \[
  \alpha^\perp=
  \alpha-X(X^\top X)^{-1}X^\top\alpha
  \]

- **Signal decay**
  \[
  IC(h)=
  \operatorname{Corr}
  (\alpha_t,r_{t\rightarrow t+h})
  \]

## Machine Learning and Forecasting

### Supervised learning losses

- **Mean squared error**
  \[
  MSE=\frac{1}{n}\sum_{i=1}^{n}(y_i-\hat y_i)^2
  \]

- **Root mean squared error**
  \[
  RMSE=\sqrt{MSE}
  \]

- **Mean absolute error**
  \[
  MAE=\frac{1}{n}\sum_{i=1}^{n}|y_i-\hat y_i|
  \]

- **Binary cross-entropy**
  \[
  \mathcal L=
  -\frac{1}{n}\sum_{i=1}^{n}
  \left[
  y_i\ln p_i+(1-y_i)\ln(1-p_i)
  \right]
  \]

- **Logistic probability**
  \[
  p(y=1\mid x)=
  \frac{1}{1+e^{-\beta^\top x}}
  \]

- **Regularized regression**
  \[
  \min_\beta
  \|y-X\beta\|_2^2+
  \lambda\|\beta\|_2^2
  \qquad\text{(ridge)}
  \]
  \[
  \min_\beta
  \|y-X\beta\|_2^2+
  \lambda\|\beta\|_1
  \qquad\text{(lasso)}
  \]

- **Elastic net**
  \[
  \min_\beta
  \|y-X\beta\|_2^2+
  \lambda_1\|\beta\|_1+
  \lambda_2\|\beta\|_2^2
  \]

### Classification metrics

- **Accuracy**
  \[
  \text{Accuracy}=
  \frac{TP+TN}{TP+TN+FP+FN}
  \]

- **Precision**
  \[
  \text{Precision}=
  \frac{TP}{TP+FP}
  \]

- **Recall**
  \[
  \text{Recall}=
  \frac{TP}{TP+FN}
  \]

- **F1 score**
  \[
  F1=
  2\frac{\text{Precision}\times\text{Recall}}
  {\text{Precision}+\text{Recall}}
  \]

- **AUC interpretation**
  \[
  AUC=\Pr(s(X^+)>s(X^-))
  \]

### Dimensionality reduction

- **Principal components**
  \[
  \Sigma v_i=\lambda_i v_i
  \]

- **Explained-variance ratio**
  \[
  EVR_i=
  \frac{\lambda_i}{\sum_j\lambda_j}
  \]

- **PCA projection**
  \[
  Z=XW_k
  \]

### Model validation

- **Train/test split objective**
  \[
  \text{Out-of-sample loss}=
  \frac{1}{n_{\text{test}}}
  \sum_{i\in\text{test}}\ell(y_i,\hat y_i)
  \]

- **Walk-forward optimization**
  \[
  \hat{\theta}_t=
  \arg\max_{\theta}
  \operatorname{Metric}
  (\text{training window ending at }t)
  \]

- **Probability of backtest overfitting**
  \[
  PBO\approx
  \Pr(\text{in-sample winner underperforms median out of sample})
  \]

- **Deflated Sharpe ratio**
  \[
  DSR=
  \Phi\left(
  \frac{SR-\widehat{SR}_0}
  {\sqrt{\operatorname{Var}(SR)}}
  \right)
  \]
  used to discount apparently strong backtests for multiple testing, non-normality, and estimation uncertainty.

## Monte Carlo and Numerics

### Simulation

- **Monte Carlo derivative-pricing estimator**
  \[
  V_0\approx
  e^{-rT}\frac{1}{N}
  \sum_{i=1}^{N}\text{Payoff}_i
  \]
  This is the standard discounted-average-payoff estimator for simulated derivative pricing. [linkedin](https://www.linkedin.com/posts/prateek964_quantfinance-mathematics-finance-activity-7478466524215697411-8bYk)

- **Monte Carlo standard error**
  \[
  SE(\hat V)=
  \frac{\operatorname{std}(X_1,\ldots,X_N)}{\sqrt N}
  \]

- **Confidence interval**
  \[
  \hat V\pm z_{\alpha/2}SE(\hat V)
  \]

- **Euler–Maruyama discretization**
  \[
  X_{t+\Delta t}=
  X_t+a(X_t,t)\Delta t+
  b(X_t,t)\sqrt{\Delta t}\,Z_t
  \]

- **GBM simulation**
  \[
  S_{t+\Delta t}=S_t
  \exp\left[
  \left(\mu-\frac12\sigma^2\right)\Delta t+
  \sigma\sqrt{\Delta t}Z_t
  \right]
  \]

- **Antithetic variates**
  \[
  \hat V_{\text{anti}}=
  \frac{1}{2N}\sum_{i=1}^{N}
  [f(Z_i)+f(-Z_i)]
  \]

- **Control-variate estimator**
  \[
  \hat{\theta}_{CV}=
  \bar X-c(\bar Y-E[Y])
  \]

- **Optimal control-variate coefficient**
  \[
  c^*=
  \frac{\operatorname{Cov}(X,Y)}
  {\operatorname{Var}(Y)}
  \]

### Numerical differentiation and PDEs

- **Forward finite difference**
  \[
  f'(x)\approx\frac{f(x+h)-f(x)}{h}
  \]

- **Central finite difference**
  \[
  f'(x)\approx
  \frac{f(x+h)-f(x-h)}{2h}
  \]

- **Second derivative**
  \[
  f''(x)\approx
  \frac{f(x+h)-2f(x)+f(x-h)}{h^2}
  \]

- **Newton–Raphson root finding**
  \[
  x_{n+1}=x_n-\frac{f(x_n)}{f'(x_n)}
  \]
  Often used to solve for implied volatility.

- **Bisection method**
  \[
  x_{n+1}=\frac{a_n+b_n}{2}
  \]

- **Finite-difference PDE approach**
  \[
  \frac{\partial V}{\partial t}
  +\mathcal LV-rV=0
  \]
  Finite-difference methods approximate the PDEs arising in derivatives pricing. [quantstart](https://www.quantstart.com/articles/Quant-Reading-List-Numerical-Methods/)

## Practical Backtest Calculations

### Strategy P&L

- **Position P&L**
  \[
  P\&L_t=q_{t-1}(P_t-P_{t-1})
  \]

- **Return on capital**
  \[
  R_t=\frac{P\&L_t}{\text{Capital}_{t-1}}
  \]

- **Long-short portfolio return**
  \[
  R_{LS,t}=
  \sum_{i\in L}w_iR_{i,t}
  -\sum_{j\in S}|w_j|R_{j,t}
  \]

- **Gross exposure**
  \[
  G=\sum_i|w_i|
  \]

- **Net exposure**
  \[
  N=\sum_iw_i
  \]

- **Turnover**
  \[
  \text{Turnover}_t=
  \frac{1}{2}\sum_i
  |w_{i,t}-w_{i,t-1}|
  \]

- **Transaction cost**
  \[
  TC_t=
  \sum_i
  |\Delta q_{i,t}|P_{i,t}
  \left(
  \text{commission}_i+
  \text{spread cost}_i+
  \text{impact cost}_i
  \right)
  \]

- **Net strategy return**
  \[
  R_t^{net}=R_t^{gross}-TC_t
  \]

- **Capacity approximation**
  \[
  \text{Capacity}
  \propto
  \frac{\text{Available Liquidity}}
  {\text{Turnover}\times\text{Market Impact}}
  \]

## How to Use This Map

A useful learning order is:

1. **Returns, probability, statistics, and regression.**
2. **Portfolio arithmetic:** covariance, optimization, factor models, risk contributions.
3. **Risk:** volatility, VaR/ES, drawdowns, stress tests.
4. **Derivatives:** no-arbitrage, Black–Scholes, Greeks, trees, Monte Carlo.
5. **Fixed income and credit:** discounting, curves, duration, default risk.
6. **Trading implementation:** signals, execution costs, slippage, market impact, backtest hygiene.
7. **Research engineering:** validation, walk-forward tests, multiple-testing control, robust optimization.

The key distinction: a formula by itself is rarely a strategy. A production quant system needs clean point-in-time data, realistic transaction costs, survivorship-bias controls, robust out-of-sample validation, position constraints, and live risk monitoring.