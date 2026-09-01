Below is a research-oriented **quant strategy cookbook** for momentum, mean reversion, pairs trading, factor portfolios, and options volatility. Each recipe specifies the intuition, formulas, trading rules, sizing, costs, validation, and common failure modes—because the signal itself is only a small part of a tradable system.

None of these is a guaranteed profitable strategy. Treat them as robust starting blueprints: use point-in-time data, realistic execution assumptions, and strict out-of-sample testing before risking capital.

## Common Framework

Every strategy should be expressed in the same pipeline:

\[
\text{Data} \rightarrow \text{Signal} \rightarrow \text{Position size} \rightarrow \text{Execution} \rightarrow \text{Costs} \rightarrow \text{Risk controls} \rightarrow \text{Evaluation}
\]

For a portfolio of \(N\) instruments, define:

\[
R_{p,t+1}=w_t^\top r_{t+1}-c_{t+1}
\]

where:

- \(w_t\) is the vector of positions decided using only information available at time \(t\).
- \(r_{t+1}\) is the next holding-period return.
- \(c_{t+1}\) is fees, bid–ask spread, slippage, market impact, financing, borrow, and other trading costs.

This timing is non-negotiable:

\[
w_t=f(\mathcal I_t)
\]

\[
\text{P\&L}_{t+1}=w_t^\top r_{t+1}
\]

Using the close of day \(t\) to compute a signal and pretending you earned day-\(t\)'s close-to-close return is look-ahead bias.

### Baseline risk controls

Use these across all five recipes:

\[
\sigma_{\text{ann}}=\sigma_{\text{daily}}\sqrt{252}
\]

\[
L_t=\min\left(L_{\max},\frac{\sigma^\star}{\hat\sigma_t}\right)
\]

where \(\sigma^\star\) is your target volatility and \(L_{\max}\) is a hard leverage cap.

A basic turnover measure:

\[
\text{Turnover}_t=
\frac{1}{2}\sum_{i=1}^{N}|w_{i,t}-w_{i,t-1}|
\]

A practical linear cost approximation:

\[
\text{Cost}_t
=
\sum_i
|w_{i,t}-w_{i,t-1}|
\cdot c_i
\]

For liquid US equities, \(c_i\) should at least include half-spread, commissions/fees, conservative slippage, and—if shorting—stock-borrow cost. For smaller names, options, futures rolls, crypto, or intraday strategies, costs can dominate the apparent edge.

### What to report

Do not judge a strategy from a single cumulative-equity curve. At minimum report:

\[
\text{Sharpe}
=
\sqrt{252}
\frac{\overline{r_p-r_f}}
{\operatorname{Std}(r_p-r_f)}
\]

\[
DD_t=\frac{E_t}{\max_{\tau \leq t}E_\tau}-1
\]

\[
\text{Maximum Drawdown}=\min_t DD_t
\]

\[
\text{CAGR}
=
\left(\frac{E_T}{E_0}\right)^{1/Y}-1
\]

Also report:

- Gross and net return.
- Annual turnover.
- Exposure by asset, sector, factor, country, and currency where applicable.
- Hit rate, average win, average loss, and tail losses.
- Rolling 12-month Sharpe and drawdown.
- Results by market regime, such as low/high volatility and bull/bear markets.
- Sensitivity to modest changes in lookback, holding period, execution delay, and costs.

## 1. Time-Series Momentum

Time-series momentum asks: **has this same instrument risen or fallen over a trailing horizon?** If it rose, go long; if it fell, go short or reduce exposure.

It is most naturally implemented across liquid futures—equity index, rates, FX, commodity, and bond futures—because shorting is symmetrical and financing is operationally cleaner than with an all-equity long-short book.

### Core signal

For asset \(i\), use a trailing log return over \(L\) periods:

\[
m_{i,t}^{(L)}
=
\ln\left(\frac{P_{i,t}}{P_{i,t-L}}\right)
\]

Binary sign signal:

\[
s_{i,t}=\operatorname{sign}(m_{i,t}^{(L)})
\]

A smoother, volatility-aware version:

\[
z_{i,t}^{\text{mom}}
=
\frac{m_{i,t}^{(L)}}{\hat\sigma_{i,t}\sqrt{L}}
\]

Then cap extreme signals:

\[
s_{i,t}
=
\operatorname{clip}
\left(
\frac{z_{i,t}^{\text{mom}}}{z_{\text{cap}}},
-1,
1
\right)
\]

### Basic recipe

| Component | Suggested starting design |
|---|---|
| Universe | Highly liquid index, government-bond, FX, commodity, and rate futures |
| Signal | 3-, 6-, 9-, or 12-month trailing return |
| Rebalance | Daily or weekly signal update; monthly is a reasonable first baseline |
| Position | Long if trailing return is positive; short if negative |
| Volatility | EWMA or 20–60 day realized volatility |
| Risk target | 8–12% annualized portfolio volatility |
| Diversification | Equal risk across contracts or asset-class sleeves |
| Costs | Include rolls, spread, impact, margin financing, and exchange/clearing fees |

### Volatility forecast

EWMA variance:

\[
\hat\sigma_{i,t}^2
=
\lambda\hat\sigma_{i,t-1}^2
+
(1-\lambda)r_{i,t-1}^2
\]

A daily decay parameter near \(0.94\) is a commonly used starting convention, though it should be tested and calibrated for your universe.

Risk-normalized raw position:

\[
\tilde w_{i,t}
=
\frac{s_{i,t}}{\hat\sigma_{i,t}}
\]

Portfolio-normalized weight:

\[
w_{i,t}
=
\frac{\tilde w_{i,t}}
{\sum_j|\tilde w_{j,t}|}
\cdot L_t
\]

A 2016 study found that much of the apparent historical strength of time-series momentum can be associated with volatility scaling; unscaled momentum and buy-and-hold may have similar cumulative-return behavior in some samples. That makes separating **signal alpha** from **volatility-targeting exposure management** essential. [sciencedirect](https://www.sciencedirect.com/science/article/abs/pii/S1386418116301379)

### Example rules

A monthly 12-month trend system:

1. At month-end \(t\), calculate each contract’s trailing 252-trading-day return.
2. Go long if it is positive; short if negative.
3. Scale each position inversely to its trailing 60-day volatility.
4. Allocate equal ex-ante risk to each asset-class sleeve.
5. Rebalance at the next session, not at the already-observed closing price.
6. Cap a single contract, asset class, and total gross leverage.
7. Include futures roll costs and conservative bid–ask/slippage assumptions.

### Stronger variants

- **Dual momentum:** require both positive absolute momentum and a cross-sectional rank above a threshold.
- **Multi-horizon ensemble:** combine 1-, 3-, 6-, and 12-month signals to reduce dependence on one parameter.
- **Moving-average trend:** trade the sign of fast minus slow moving average.
- **Breakout:** long when price exceeds its \(L\)-day high; short below its \(L\)-day low.
- **Regime filters:** reduce gross risk during liquidity stress or unusually correlated drawdowns, rather than turning the signal on/off based only on recent P&L.

### Failure modes

- A trend reverses sharply, creating “whipsaw.”
- Volatility targeting deleverages after a crisis move, potentially after losses have occurred.
- Futures data is mishandled: incorrect continuous contracts, roll adjustments, or expired-contract prices can create fake signals.
- Portfolio is unintentionally concentrated in one macro bet—for example, short equities, long bonds, long USD, and long volatility exposure all reflecting a single risk-off view.
- Results depend on one lookback or a narrow historical episode.

## 2. Cross-Sectional Mean Reversion

Cross-sectional mean reversion asks: **among comparable assets, which have moved unusually far versus peers and may partially reverse?** A practical form ranks a liquid stock universe by short-horizon residual return, buys relative underperformers, and shorts relative outperformers.

This is different from “buy a stock because its price is below its 20-day average.” Cross-sectional designs can remove part of broad market and sector movement, which matters for a market-neutral strategy.

### Core signal

For each stock \(i\), calculate a short-horizon return:

\[
r_{i,t}^{(L)}
=
\ln\left(\frac{P_{i,t}}{P_{i,t-L}}\right)
\]

Cross-sectional standardization:

\[
z_{i,t}
=
\frac{r_{i,t}^{(L)}-\bar r_t^{(L)}}
{\operatorname{Std}_i(r_{i,t}^{(L)})}
\]

Contrarian score:

\[
s_{i,t}=-z_{i,t}
\]

A more robust version uses industry-adjusted residual returns:

\[
r_{i,t}
=
\alpha_t+\beta_{m,i}r_{m,t}
+\sum_g \gamma_{g,t}\mathbf{1}_{i\in g}
+\epsilon_{i,t}
\]

Then trade the residual:

\[
s_{i,t}=-z(\epsilon_{i,t}^{(L)})
\]

### Basic recipe

| Component | Suggested starting design |
|---|---|
| Universe | Large, liquid, borrowable equities |
| Signal horizon | 1–5 trading days for short-term reversal |
| Rebalance | Daily, usually near close or next open |
| Long book | Lowest 10–20% by residual short-horizon return |
| Short book | Highest 10–20% by residual short-horizon return |
| Neutrality | Dollar, beta, sector, and ideally industry neutral |
| Position weights | Equal-weight, inverse-volatility, or rank-weighted |
| Exit | Rebalance daily; optional signal-decay or holding cap |
| Costs | High priority—short-horizon strategies create turnover |

### Market and sector neutrality

Dollar neutrality:

\[
\sum_i w_i=0
\]

Beta neutrality:

\[
\sum_i w_i\beta_i=0
\]

Sector neutrality for each sector \(g\):

\[
\sum_{i\in g}w_i=0
\]

A residual return model, followed by explicit constraints, is usually more robust than hoping equal dollar long/short automatically removes market and sector risk.

### Position sizing

Rank-based weights:

\[
w_i
\propto
\begin{cases}
+\operatorname{rank\_strength}_i, & i \in \text{bottom signal bucket} \\
-\operatorname{rank\_strength}_i, & i \in \text{top signal bucket} \\
0, & \text{otherwise}
\end{cases}
\]

Inverse-volatility adjustment:

\[
\tilde w_i=\frac{w_i}{\hat\sigma_i}
\]

Then re-center the long and short books to satisfy neutrality constraints.

### Useful filters

- Trade only names above a minimum average-dollar-volume threshold.
- Exclude names with hard-to-borrow status or prohibitively high borrow rates.
- Exclude earnings days, merger situations, halts, extreme gaps, or recent index additions if your data and execution model do not handle them.
- Neutralize common exposures: sector, industry, size, beta, value, momentum, and volatility.
- Use a “no-trade band” so very small score changes do not produce churn.

Example no-trade rule:

\[
\text{Trade only if } |w_{i,t}^{\text{target}}-w_{i,t-1}|>\delta
\]

### Failure modes

- Apparent reversal is actually compensation for earnings/news risk, liquidity risk, or short-sale constraints.
- The top “winners” are difficult or expensive to borrow.
- Corporate-action adjustments or survivorship-free universe construction are missing.
- Backtests assume execution at the closing price that generated the signal.
- Market-neutral does not mean risk-neutral: a book can retain factor, liquidity, crash, and crowded-short risk.
- Net P&L vanishes after turnover and borrow costs.

## 3. Cointegration Pairs Trading

Pairs trading attempts to exploit temporary dislocations in a **stationary spread** between two economically related instruments. The key distinction: high correlation is not sufficient. The target is a relationship whose residual/spread appears mean-reverting.

Cointegration means that two nonstationary time series can share a stable long-run relation, such that a particular linear combination is stationary. [arxiv](https://arxiv.org/html/2412.12555v1)

### Pair construction

For price series \(Y_t\) and \(X_t\), estimate:

\[
Y_t=\alpha+\beta X_t+\epsilon_t
\]

The hedge ratio is:

\[
\hat\beta
=
\frac{\operatorname{Cov}(X,Y)}
{\operatorname{Var}(X)}
\]

Define spread:

\[
s_t=Y_t-\hat\alpha-\hat\beta X_t
\]

If \(s_t\) is stationary, it is a candidate mean-reverting spread.

### Signal

Compute rolling spread z-score:

\[
z_t=
\frac{s_t-\mu_{s,t}^{(L)}}
{\sigma_{s,t}^{(L)}}
\]

Basic entries and exits:

| Condition | Trade action |
|---|---|
| \(z_t \geq z_{\text{entry}}\) | Short spread: short \(Y\), long \(\beta X\) |
| \(z_t \leq -z_{\text{entry}}\) | Long spread: long \(Y\), short \(\beta X\) |
| \(|z_t| \leq z_{\text{exit}}\) | Close or sharply reduce |
| \(|z_t| \geq z_{\text{stop}}\) | Risk stop / reassess model |
| Holding period exceeds cap | Close regardless of z-score |

Reasonable *research starting points* might be \(z_{\text{entry}}=2\), \(z_{\text{exit}}=0.25\) to \(0.5\), and \(z_{\text{stop}}=3\) to \(4\). They are not universal production parameters.

### Half-life estimation

Fit:

\[
\Delta s_t=a+b s_{t-1}+\epsilon_t
\]

For \(b<0\), approximate half-life:

\[
t_{1/2}\approx-\frac{\ln 2}{b}
\]

Use half-life as a sanity check:

- A half-life of a few days may fit an actively traded daily strategy.
- A half-life of many months may not be tradable after costs and regime risk.
- An implausibly tiny or unstable half-life may indicate data leakage or a poor regression specification.

### Dollar-neutral pair construction

If you buy \(Y\) and short \(\beta X\), dollar-neutral quantities can be approximated as:

\[
q_Y=\frac{G/2}{P_Y}
\]

\[
q_X=\frac{\beta G/2}{P_X}
\]

where \(G\) is gross notional. Then refine for beta neutrality, volatility, contract multipliers, borrow availability, and financing.

### Candidate selection process

1. Start with an economically sensible universe: same industry, share classes, closely related ETFs, ADR/local listings, or linked ETFs and futures.
2. Filter for liquidity, common trading hours, borrowability, and reliable corporate-action-adjusted data.
3. Fit hedge ratio only using a rolling training window.
4. Test residual stationarity using Engle–Granger or Johansen methods.
5. Require stability across several rolling windows, not one in-sample test.
6. Estimate spread half-life and historical turnover.
7. Reserve a fully out-of-sample period for trade simulation.
8. Retire pairs when relationship diagnostics deteriorate.

Research on ETF pairs from 2000–2024 emphasizes that cointegration stability matters, and that lower z-score thresholds may raise trade frequency and profits while also increasing volatility and drawdowns. [link.springer](https://link.springer.com/article/10.1057/s41260-025-00416-0)

### Error-correction model

A more explicit approach:

\[
\Delta Y_t
=
a
+
\gamma(Y_{t-1}-\beta X_{t-1})
+
\delta \Delta X_t
+
\epsilon_t
\]

The term:

\[
Y_{t-1}-\beta X_{t-1}
\]

is the prior equilibrium error. A negative and statistically meaningful \(\gamma\) supports the idea that deviations tend to correct.

### Failure modes

- A merger, spin-off, index reconstitution, product change, or capital-structure event permanently changes the relationship.
- Cointegration was only in-sample luck.
- Daily closing-price spread is tradable only with costs and timing assumptions that prove unrealistic.
- A short leg is unborrowable or borrow cost destroys expected spread return.
- “Mean reversion” continues far beyond a fixed z-score stop because the relationship structurally broke.
- Pair-level independence is an illusion: dozens of equity pairs can all load heavily on the same sector or market factor.

## 4. Multifactor Equity Portfolio

A factor portfolio ranks stocks using persistent characteristics—such as value, quality/profitability, momentum, low risk, and size—then builds a diversified long-short or long-only portfolio while neutralizing unwanted exposures.

The Fama–French framework introduced market, size, and value factors, with later extensions adding profitability and investment. The official Kenneth French data library provides historical factor and portfolio data, including 3-factor and 5-factor series and related portfolio sorts. [wrds-www.wharton.upenn](https://wrds-www.wharton.upenn.edu/pages/about/data-vendors/fama-french-portfolios-factors/)

### Factor score construction

For stock \(i\), define standardized factor scores:

\[
z_{i,k}
=
\frac{x_{i,k}-\mu_k}{\sigma_k}
\]

Use winsorization before standardization to prevent a few extreme observations from dominating:

\[
x_{i,k}^{\text{win}}
=
\min(\max(x_{i,k},q_{0.01}),q_{0.99})
\]

Composite alpha score:

\[
A_i
=
a_Vz_{i,\text{value}}
+
a_Qz_{i,\text{quality}}
+
a_Mz_{i,\text{momentum}}
+
a_Lz_{i,\text{low-risk}}
\]

You can use equal weights initially:

\[
a_V=a_Q=a_M=a_L=\frac{1}{4}
\]

But do not optimize factor weights aggressively on a single historical sample.

### Example factor definitions

| Factor | Example metrics | Direction |
|---|---|---|
| Value | Book-to-market, earnings yield, free-cash-flow yield, EBITDA/EV | Higher is cheaper / positive score |
| Quality | ROE, gross profitability, operating margin, low accruals, conservative leverage | Higher quality / positive score |
| Momentum | 12–1 month return, 6–1 month return, residual momentum | Higher past relative strength / positive score |
| Low risk | Low beta, low realized volatility, low idiosyncratic volatility | Lower risk / positive score |
| Size | Log market capitalization | Often used as a control or explicit small-cap factor |
| Investment | Asset-growth or investment rate | Lower aggressive investment commonly receives higher score |

The Fama–French five-factor model is intended to capture patterns tied to size, value, profitability, and investment in average returns, expanding on the original three-factor framework. [papers.ssrn](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=2287202)

### A practical 12–1 momentum definition

Skip the most recent month to reduce short-term reversal and microstructure effects:

\[
\text{Mom}_{i,t}^{12-1}
=
\ln\left(
\frac{P_{i,t-21}}
{P_{i,t-252}}
\right)
\]

### Cross-sectional rank approach

Ranks are often more robust than raw values:

\[
\operatorname{RankPct}(x_i)
=
\frac{\operatorname{rank}(x_i)-1}{N-1}
\]

Convert rank percentile into a centered score:

\[
z_i^{\text{rank}}
=
2\operatorname{RankPct}(x_i)-1
\]

This constrains the influence of accounting outliers and makes factor metrics on different scales easier to combine.

### Portfolio construction

One simple long-short design:

- Go long the top 20% of composite scores.
- Go short the bottom 20%.
- Use rank-weighted or inverse-volatility-adjusted position weights.
- Rebalance monthly.
- Enforce sector, industry, beta, country, size, and single-name constraints.
- Use turnover controls and gradual rebalancing.

Constrained optimization:

\[
\max_w
\left[
w^\top A
-
\frac{\gamma}{2}w^\top\Sigma w
-
\lambda_{\text{turn}}\|w-w_{\text{old}}\|_1
\right]
\]

Subject to:

\[
\sum_i w_i=0
\]

\[
w^\top\beta=0
\]

\[
\sum_{i\in g}w_i=0
\quad \forall g
\]

\[
|w_i|\leq w_{\max}
\]

\[
\sum_i |w_i| \leq G_{\max}
\]

Here:

- \(A\) is the alpha score vector.
- \(\Sigma\) is a covariance matrix.
- \(\gamma\) controls risk aversion.
- \(\lambda_{\text{turn}}\) penalizes churn.

### Fundamental data rules

Use only information that would actually have been known on the trading date.

For example, for a quarterly fundamental reported on date \(d_{\text{report}}\):

\[
x_{i,t}=
\begin{cases}
\text{latest publicly available reported value}, & t \geq d_{\text{report}}+\text{lag}\\
\text{previous value}, & \text{otherwise}
\end{cases}
\]

Use a conservative publication lag. “Fiscal quarter ending March 31” is not the same as “information tradable on March 31.”

### Failure modes

- Survivorship bias from using today’s index constituents in historical backtests.
- Look-ahead bias in accounting data, restatements, or analyst estimates.
- Value traps, crowded quality/momentum trades, or factor crashes.
- Exposure drift: a value portfolio unintentionally becomes a small-cap, cyclical, or financials portfolio.
- Too much turnover from noisy rank changes.
- Sparse coverage or bad fundamentals in small-cap stocks.
- Combining factors without checking whether they overlap or cancel one another.

## 5. Options Volatility Strategies

Volatility trading is not simply “buy options when you think the market moves.” You are usually trading the gap between:

\[
\text{Implied volatility}
\]

and

\[
\text{future realized volatility}
\]

as well as skew, term structure, jump risk, gamma exposure, liquidity, and dynamic hedging costs.

An option’s implied volatility is the volatility backed out of the market price using an option-pricing model; option risk is commonly decomposed with delta, gamma, theta, vega, and related Greeks. [investopedia](https://www.investopedia.com/terms/o/option.asp)

### Core volatility measures

Daily log return:

\[
r_t=\ln(P_t/P_{t-1})
\]

Annualized realized volatility over \(L\) daily observations:

\[
\sigma_{\text{realized},t}
=
\sqrt{
252
\cdot
\frac{1}{L-1}
\sum_{j=0}^{L-1}
(r_{t-j}-\bar r)^2
}
\]

Simple forecast using EWMA:

\[
\hat\sigma_{t+1}^2
=
\lambda \hat\sigma_t^2
+
(1-\lambda)r_t^2
\]

Variance risk premium estimate:

\[
\text{VRP}_t
=
\sigma_{\text{IV},t}^2
-
E_t[\sigma_{\text{realized},t\rightarrow T}^2]
\]

If implied variance greatly exceeds a carefully estimated future realized variance, an option-selling trade may appear attractive—but it is also exposed to crash, jump, liquidity, and model risk. The premium exists partly because those risks are real.

### Black–Scholes pricing

For a European call with continuous dividend yield \(q\):

\[
C
=
S_0e^{-qT}N(d_1)
-
Ke^{-rT}N(d_2)
\]

\[
d_1
=
\frac{
\ln(S_0/K)
+
(r-q+\frac{1}{2}\sigma^2)T
}
{\sigma\sqrt T}
\]

\[
d_2=d_1-\sigma\sqrt T
\]

In practice, you invert the model numerically to find implied volatility:

\[
\sigma_{\text{IV}}
=
\arg\min_{\sigma>0}
\left[
C_{\text{BS}}(\sigma)-C_{\text{market}}
\right]^2
\]

### Greeks

| Greek | Meaning | Approximate role |
|---|---|---|
| Delta \(\Delta\) | Sensitivity to underlying-price move | Directional exposure |
| Gamma \(\Gamma\) | Change in delta as price moves | Convexity; long gamma benefits from large moves when hedged well |
| Vega \(\nu\) | Sensitivity to implied-volatility change | Exposure to IV repricing |
| Theta \(\Theta\) | Sensitivity to time passing | Option time decay |
| Rho \(\rho\) | Sensitivity to interest rates | Usually secondary for short-dated equity options |

For a portfolio:

\[
\Delta_{\text{book}}=\sum_i q_i\Delta_i
\]

\[
\Gamma_{\text{book}}=\sum_i q_i\Gamma_i
\]

\[
\text{Vega}_{\text{book}}=\sum_i q_i\nu_i
\]

A book that is “delta neutral” can still be very risky if it has large negative gamma, negative vega, concentrated expiry exposure, or short crash-sensitive skew.

### Recipe A: Delta-hedged long straddle

**Goal:** Buy implied volatility when you expect subsequent realized volatility to exceed the volatility embedded in the options, enough to cover premium decay, bid–ask spread, commissions, and hedge costs.

At-the-money straddle cost:

\[
\Pi_0=C_0+P_0
\]

Initial delta:

\[
\Delta_0=\Delta_C+\Delta_P
\]

Hedge underlying shares to offset delta:

\[
q_{\text{hedge}}=-\Delta_{\text{book}}
\]

P&L decomposition, conceptually:

\[
d\Pi
\approx
\Delta dS
+
\frac{1}{2}\Gamma(dS)^2
+
\nu d\sigma_{\text{IV}}
+
\Theta dt
\]

After delta hedging, the intended exposure is primarily:

\[
d\Pi_{\text{hedged}}
\approx
\frac{1}{2}\Gamma(dS)^2
+
\nu d\sigma_{\text{IV}}
+
\Theta dt
-
\text{hedging costs}
\]

Trade design:

| Component | Starting specification |
|---|---|
| Instrument | Liquid at-the-money listed options |
| Tenor | Often 20–60 calendar days, depending on liquidity and event horizon |
| Entry | Forecast realized vol exceeds IV by a margin covering expected costs |
| Hedge | Delta hedge on schedule or delta threshold |
| Exit | Before expiry, after IV repricing, or when forecast edge disappears |
| Limits | Cap vega, gamma, concentration by name/expiry, and event exposure |

The central risk: long options may lose from time decay even if your directional view is correct but the move is too small, too slow, or happens after expiry.

### Recipe B: Delta-hedged short straddle / short variance

**Goal:** Sell rich implied volatility while dynamically hedging delta.

This is structurally similar to being short insurance. It can earn frequent small gains and occasionally suffer severe losses.

Basic setup:

\[
\text{Sell ATM call}+\text{sell ATM put}
\]

Delta hedge:

\[
q_{\text{hedge}}=-\Delta_{\text{book}}
\]

Key constraints:

- Never size from premium collected alone.
- Stress gap moves, volatility spikes, skew shifts, and liquidity disappearance.
- Cap gross and net short gamma.
- Avoid mechanically selling through known event risk without explicitly pricing it.
- Model early exercise and assignment for American equity options.
- Include realistic bid–ask and dynamic-hedging transaction costs.

A short-volatility system should survive scenarios such as:

\[
S_{t+1}=S_t(1-0.10)
\]

\[
\sigma_{\text{IV},t+1}
=
\sigma_{\text{IV},t}
+
0.20
\]

and worse. If the strategy fails under a plausible overnight gap or volatility shock, it is not appropriately sized.

### Recipe C: Implied-versus-realized volatility screen

For each underlying \(i\):

\[
\text{Edge}_{i,t}
=
\sigma_{\text{IV},i,t}
-
\hat\sigma_{\text{future realized},i,t}
\]

A variance-scale alternative:

\[
\text{Edge}^{\text{var}}_{i,t}
=
\sigma_{\text{IV},i,t}^2
-
\hat\sigma_{\text{realized},i,t}^2
\]

Then normalize by uncertainty and implementation cost:

\[
\text{TradeScore}_{i,t}
=
\frac{
\text{Expected Vol Edge}_{i,t}
-
\text{Cost Buffer}_{i,t}
}{
\text{Forecast Uncertainty}_{i,t}
}
\]

Do not compare an implied volatility with trailing realized volatility as if they are identical. IV is forward-looking, maturity-specific, strike-specific, and includes risk premia. Your realized-volatility forecast must match the option’s future horizon.

### Recipe D: Term-structure signal

For two maturities \(T_1<T_2\):

\[
\text{TermSlope}
=
\sigma_{\text{IV}}(T_2)-\sigma_{\text{IV}}(T_1)
\]

Or normalized:

\[
\text{TermSlopeRatio}
=
\frac{\sigma_{\text{IV}}(T_1)}
{\sigma_{\text{IV}}(T_2)}
\]

This can inform calendar spreads, but term structure is heavily affected by event risk, roll-down, liquidity, supply/demand, and the fact that different tenors are not interchangeable exposures.

### Recipe E: Skew signal

Put-versus-call skew around matched deltas:

\[
\text{Skew}_{25\Delta}
=
\sigma_{\text{put},25\Delta}
-
\sigma_{\text{call},25\Delta}
\]

A common alternative:

\[
\text{Risk Reversal}_{25\Delta}
=
\sigma_{\text{call},25\Delta}
-
\sigma_{\text{put},25\Delta}
\]

Equity-index downside skew often reflects demand for crash protection, not a free mispricing.

### Model-free implied variance

The VIX-style methodology derives a model-free implied variance estimate from a strip of out-of-the-money puts and calls. The generalized discrete formula is:

\[
\sigma^2
=
\frac{2}{T}
\sum_i
\frac{\Delta K_i}{K_i^2}
e^{rT}Q(K_i)
-
\frac{1}{T}
\left(
\frac{F}{K_0}-1
\right)^2
\]

where \(Q(K_i)\) is the selected out-of-the-money option price, \(F\) is the forward level, \(K_0\) is the first strike below the forward, and \(\Delta K_i\) is strike spacing. Cboe’s methodology uses this variance calculation and then interpolates across expiries to obtain constant-maturity volatility indices. [cdn.cboe](https://cdn.cboe.com/api/global/us_indices/governance/Cboe_Volatility_Index_Mathematics_Methodology.pdf)

### Failure modes

- Selling high IV before an actual jump, gap, earnings surprise, or systemic shock.
- Ignoring American exercise, dividends, hard-to-borrow effects, and assignment.
- Treating stale midquotes as executable prices.
- Comparing 30-day IV with 5-day historical realized volatility.
- Ignoring skew and term structure while calling a trade “vega neutral.”
- Underestimating the cost and path dependence of delta hedging.
- Overconcentration in the same expiry, underlying, sector, or macro shock exposure.

## Research Checklist

Before considering any recipe credible, require all of the following:

1. **Point-in-time universe:** Historical constituents, delistings, corporate actions, and data availability must reflect what was tradable then.
2. **No leakage:** Lag prices, fundamentals, estimates, and labels correctly. Fit scalers and models only on prior data.
3. **Walk-forward testing:** Train on a historical window, trade a later window, roll forward, and concatenate only genuine out-of-sample results.
4. **Parameter stability:** Test sensible ranges rather than presenting only the best parameter combination.
5. **Cost sensitivity:** Increase assumed spread, slippage, borrow, and impact. An edge that disappears under mild cost changes is fragile.
6. **Capacity testing:** Estimate participation rate:
   \[
   \text{Participation}_t=\frac{|Q_t|}{ADV_t}
   \]
   and reject strategies requiring unrealistic fractions of daily volume.
7. **Stress tests:** Run crisis periods, volatility spikes, rapid reversals, borrow recalls, gaps, and correlation breakdowns.
8. **Exposure attribution:** Decompose P&L into market beta, sector, style factors, volatility, carry, liquidity, and residual alpha.
9. **Paper trade:** Compare live signal timestamps, assumed fills, and actual executable prices before scaling.
10. **Kill rules:** Predetermine maximum drawdown, model-break diagnostics, data-quality exceptions, and position-reduction procedures.

## Implementation Order

Given that you work comfortably with Python, the most productive build order is:

1. Build a **daily-bar backtesting engine** with delayed fills, realistic costs, position limits, turnover accounting, and performance reports.
2. Add a **time-series momentum** strategy across a small liquid ETF or futures-like proxy universe.
3. Add **cross-sectional reversal** only after you can enforce beta/sector neutrality and model shorting/borrow costs.
4. Add **cointegrated pairs** with rolling hedge-ratio estimation, stationarity diagnostics, half-life filters, and pair retirement logic.
5. Add **factor portfolios** after you obtain point-in-time fundamental data; this is substantially harder than it appears with free datasets.
6. Treat **options volatility** as a separate system requiring an options-chain database, contract-aware backtesting, surface/Greek calculations, and realistic quote/execution assumptions.

The highest-value early project is usually a diversified, volatility-managed momentum system: it has transparent signal logic, lower dependence on accounting datasets, and less sensitivity to intraday microstructure than short-horizon equity mean reversion or delta-hedged options trading. But even that strategy only becomes meaningful after costs, instrument rolls, position sizing, and out-of-sample validation are modeled honestly. [sciencedirect](https://www.sciencedirect.com/science/article/abs/pii/S1386418116301379)