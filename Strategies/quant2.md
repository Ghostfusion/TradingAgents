## 1. Asset Returns & Time Series Statistics

**Simple & Log Returns**

* Simple Return: $R_t = \frac{P_t - P_{t-1}}{P_{t-1}}$
* Continuous/Log Return: $r_t = \ln\left(\frac{P_t}{P_{t-1}}\right) = \ln(P_t) - \ln(P_{t-1})$

**Moments of Distribution**

* Expected Return (Mean): $\mu = \mathbb{E}[R] = \frac{1}{N}\sum_{i=1}^N R_i$
* Variance & Volatility: $\sigma^2 = \frac{1}{N-1}\sum_{i=1}^N (R_i - \mu)^2, \quad \sigma = \sqrt{\sigma^2}$
* Sample Skewness: $S = \frac{\frac{1}{N}\sum_{i=1}^N (R_i - \mu)^3}{\sigma^3}$
* Excess Kurtosis: $K = \frac{\frac{1}{N}\sum_{i=1}^N (R_i - \mu)^4}{\sigma^4} - 3$

**Volatility Scaling**

* Annualized Volatility: $\sigma_{\text{ann}} = \sigma_{\text{daily}} \times \sqrt{252}$

---

## 2. Stochastic Calculus & Asset Price Dynamics

**Itô's Lemma**
For an Itô drift-diffusion process $dX_t = \mu_t dt + \sigma_t dW_t$ and a smooth function $f(t, X_t)$:


$$df = \left( \frac{\partial f}{\partial t} + \mu_t \frac{\partial f}{\partial x} + \frac{1}{2}\sigma_t^2 \frac{\partial^2 f}{\partial x^2} \right) dt + \sigma_t \frac{\partial f}{\partial x} dW_t$$

**Geometric Brownian Motion (GBM)**

* SDE: $dS_t = \mu S_t dt + \sigma S_t dW_t$
* Exact Solution: $S_t = S_0 \exp\left( \left(\mu - \frac{1}{2}\sigma^2\right)t + \sigma W_t \right)$

**Mean-Reverting Ornstein-Uhlenbeck (OU) Process**

* SDE: $dX_t = \theta (\mu - X_t)dt + \sigma dW_t$
* Half-life of Mean Reversion: $t_{1/2} = \frac{\ln(2)}{\theta}$

---

## 3. Derivatives Pricing & The "Greeks"

**Black-Scholes-Merton Partial Differential Equation (PDE)**


$$\frac{\partial V}{\partial t} + r S \frac{\partial V}{\partial S} + \frac{1}{2}\sigma^2 S^2 \frac{\partial^2 V}{\partial S^2} - rV = 0$$

**Black-Scholes European Call ($C$) & Put ($P$) Formulas**


$$C = S_0 N(d_1) - K e^{-rT} N(d_2), \quad P = K e^{-rT} N(-d_2) - S_0 N(-d_1)$$


Where:


$$d_1 = \frac{\ln(S_0 / K) + \left(r + \frac{1}{2}\sigma^2\right)T}{\sigma \sqrt{T}}, \quad d_2 = d_1 - \sigma \sqrt{T}$$

**Put-Call Parity**


$$C - P = S_0 - K e^{-rT}$$

**Primary Greeks (Sensitivities)**

* Delta ($\Delta$): $\frac{\partial V}{\partial S} = N(d_1)$ (for a standard call)
* Gamma ($\Gamma$): $\frac{\partial^2 V}{\partial S^2} = \frac{N'(d_1)}{S_0 \sigma \sqrt{T}}$
* Vega ($\mathcal{V}$): $\frac{\partial V}{\partial \sigma} = S_0 \sqrt{T} N'(d_1)$
* Theta ($\Theta$): $\frac{\partial V}{\partial t} = -\frac{S_0 N'(d_1)\sigma}{2\sqrt{T}} - rKe^{-rT}N(d_2)$ (for call)
* Rho ($\rho$): $\frac{\partial V}{\partial r} = K T e^{-rT} N(d_2)$

**Heston Stochastic Volatility Model**


$$dS_t = \mu S_t dt + \sqrt{v_t} S_t dW_t^S$$

$$dv_t = \kappa(\theta - v_t)dt + \xi \sqrt{v_t} dW_t^v, \quad dW_t^S dW_t^v = \rho dt$$

---

## 4. Modern Portfolio Theory (MPT) & Asset Pricing

**Portfolio Expected Return & Variance**

* Return: $\mathbb{E}[R_p] = \mathbf{w}^T \boldsymbol{\mu} = \sum_{i=1}^n w_i \mathbb{E}[R_i]$
* Variance: $\sigma_p^2 = \mathbf{w}^T \boldsymbol{\Sigma} \mathbf{w} = \sum_{i}\sum_{j} w_i w_j \text{Cov}(R_i, R_j)$

**Markowitz Mean-Variance Optimization**


$$\min_{\mathbf{w}} \frac{1}{2}\mathbf{w}^T \boldsymbol{\Sigma} \mathbf{w} - \lambda \mathbf{w}^T \boldsymbol{\mu} \quad \text{s.t.} \quad \mathbf{w}^T \mathbf{1} = 1$$

* Global Minimum Variance Portfolio (Analytical): $\mathbf{w}_{\text{GMV}} = \frac{\boldsymbol{\Sigma}^{-1}\mathbf{1}}{\mathbf{1}^T \boldsymbol{\Sigma}^{-1}\mathbf{1}}$

**Capital Asset Pricing Model (CAPM)**


$$\mathbb{E}[R_i] = R_f + \beta_i (\mathbb{E}[R_m] - R_f)$$

$$\beta_i = \frac{\text{Cov}(R_i, R_m)}{\text{Var}(R_m)}$$

**Factor Models**

* Fama-French 3-Factor:

$$\mathbb{E}[R_i] - R_f = \beta_{i,m}(R_m - R_f) + \beta_{i,s}\text{SMB} + \beta_{i,v}\text{HML}$$


* Carhart 4-Factor: Adds momentum ($\beta_{i,w}\text{WML}$)
* Black-Litterman Combined Return Vector:

$$\mathbb{E}[R] = \left[(\tau \boldsymbol{\Sigma})^{-1} + \mathbf{P}^T \boldsymbol{\Omega}^{-1} \mathbf{P}\right]^{-1} \left[(\tau \boldsymbol{\Sigma})^{-1} \boldsymbol{\Pi} + \mathbf{P}^T \boldsymbol{\Omega}^{-1} \mathbf{Q}\right]$$



---

## 5. Performance, Alpha & Trade Metrics

| Metric | Formula | Description |
| --- | --- | --- |
| **Sharpe Ratio** | $\text{SR} = \frac{\mathbb{E}[R_p - R_f]}{\sigma_p}$ | Excess return per unit of total risk. |
| **Sortino Ratio** | $\text{Sortino} = \frac{\mathbb{E}[R_p - R_f]}{\sigma_d}, \quad \sigma_d = \sqrt{\frac{1}{N}\sum \min(0, R_t - R_f)^2}$ | Penalizes downside volatility only. |
| **Information Ratio (IR)** | $\text{IR} = \frac{\mathbb{E}[R_p - R_b]}{\sigma(R_p - R_b)} = \frac{\alpha}{\text{Tracking Error}}$ | Active return per unit of active benchmark risk. |
| **Treynor Ratio** | $\text{TR} = \frac{\mathbb{E}[R_p - R_f]}{\beta_p}$ | Return earned in excess of guaranteed return per systematic risk. |
| **Calmar Ratio** | $\text{Calmar} = \frac{\text{CAGR}}{\vert{}\text{Max Drawdown}\vert{}}$ | Compound return over maximum peak-to-trough drop. |
| **Maximum Drawdown (MDD)** | $\text{MDD} = \max_{\tau \in [0, t]} \left( \frac{\max_{s \in [0, \tau]} P_s - P_\tau}{\max_{s \in [0, \tau]} P_s} \right)$ | Largest historical drop from peak to trough. |
| **Fundamental Law of Active Mgmt** | $\text{IR} \approx \text{IC} \times \sqrt{\text{BR}}$ | IC = Information Coefficient, BR = Breadth of bets. |

---

## 6. Quantitative Risk Management

**Value-at-Risk (VaR)**

* Parametric (Normal) VaR: $\text{VaR}_\alpha = - (\mu \Delta t + z_\alpha \sigma \sqrt{\Delta t}) \times V_{\text{portfolio}}$
* Historical / Non-parametric VaR: $\text{VaR}_\alpha = -\inf \{ l \in \mathbb{R} : P(L > l) \le 1 - \alpha \}$

**Conditional Value-at-Risk (CVaR / Expected Shortfall - ES)**


$$\text{ES}_\alpha = \mathbb{E}[L \mid L \ge \text{VaR}_\alpha] = \frac{1}{1-\alpha}\int_\alpha^1 \text{VaR}_u du$$

**Credit Risk & Default Intensity**

* Hazard Rate Survival Probability: $P(\tau > t) = \exp\left(-\int_0^t \lambda(s)ds\right)$
* Merton Structural Model (Equity as a Call Option on Firm Assets):

$$E = V_A N(d_1) - D e^{-rT} N(d_2)$$



---

## 7. Fixed Income & Interest Rate Models

**Bond Pricing & Duration**

* Present Value of Bond: $P = \sum_{t=1}^T \frac{C}{(1+y)^t} + \frac{M}{(1+y)^T}$
* Macaulay Duration: $D_{\text{mac}} = \frac{\sum_{t=1}^T \frac{t \cdot C_t}{(1+y)^t}}{P}$
* Modified Duration: $D_{\text{mod}} = \frac{D_{\text{mac}}}{1 + y/k}$
* DV01 (Dollar Value of an 01): $\text{DV01} = -\frac{\Delta P}{10,000 \times \Delta y} \approx D_{\text{mod}} \times P \times 0.0001$
* Convexity: $C = \frac{1}{P(1+y)^2} \sum_{t=1}^T \frac{C_t (t^2 + t)}{(1+y)^t} \implies \frac{\Delta P}{P} \approx -D_{\text{mod}} \Delta y + \frac{1}{2} C (\Delta y)^2$

**Short-Rate Models**

* Vasicek (Mean-Reverting Normal): $dr_t = a(b - r_t)dt + \sigma dW_t$
* Cox-Ingersoll-Ross (CIR - Non-negative rates): $dr_t = a(b - r_t)dt + \sigma \sqrt{r_t} dW_t$
* Hull-White (Time-varying baseline calibration): $dr_t = (\theta(t) - a r_t)dt + \sigma dW_t$

---

## 8. Market Microstructure & Execution Algorithms

**Volume-Weighted Average Price (VWAP)**


$$\text{VWAP} = \frac{\sum_{i=1}^n P_i \cdot V_i}{\sum_{i=1}^n V_i}$$

**Time-Weighted Average Price (TWAP)**


$$\text{TWAP} = \frac{1}{N}\sum_{t=1}^N P_t$$

**Almgren-Chriss Optimal Execution Framework**
Balances market impact against volatility risk over trade horizon $T$:


$$\min_{\{n_k\}} \mathbb{E}[x] + \lambda \mathbb{V}[x]$$

* Total Cost: $\text{Impact}(v) = \text{Permanent Impact} (\gamma v) + \text{Temporary Impact} (\eta v^2) + \text{Variance}(\sigma^2 \Delta t)$

**Roll Model (Effective Bid-Ask Spread Estimation)**


$$\text{Spread} = 2 \sqrt{-\text{Cov}(\Delta P_t, \Delta P_{t-1})}$$


(where $\text{Cov}(\Delta P_t, \Delta P_{t-1}) < 0$)