Yes. Financial analysts, index providers, and risk managers use specific quantitative formulas to measure ownership concentration, liquidity constraints, and price impact risk.

---

### 1. Free-Float Factor (Investable Weight Factor - IWF)

Used by index providers (S&P, MSCI) to scale down a company's market cap for index inclusion and passive allocation:

$$IWF = \frac{\text{Float Shares}}{\text{Total Shares Outstanding}} = \frac{\text{Float Market Cap}}{\text{Total Market Cap}}$$

* **Interpretation:** If $IWF < 0.50$, the stock is subject to structural passive under-allocation. For Thomson Reuters ($IWF \approx 0.30$), only 30% of its total equity value is eligible for index weighting.

---

### 2. Float Turnover Ratio

Measures how quickly the tradable share supply changes hands over a given timeframe (typically daily or annualized):

$$\text{Float Turnover} = \frac{\text{Average Daily Volume (ADV)}}{\text{Float Shares}}$$

* **Interpretation:**
* **Low Turnover ($< 0.5\%$ daily):** Low liquidity; entering or exiting large positions causes significant price slippage.
* **Extreme Turnover ($> 50\text{--}100\%$ daily):** Typical in meme stocks or micro-float squeezes, indicating speculative churn and heightened crash risk.



---

### 3. Amihud Illiquidity Measure ($ILLIQ$)

The standard academic and quantitative metric to calculate **price impact per dollar traded** (how sensitive the stock price is to trading volume):

$$ILLIQ = \frac{1}{N} \sum_{t=1}^{N} \frac{\vert{}R_t\vert{}}{\text{Dollar Volume}_t} = \frac{1}{N} \sum_{t=1}^{N} \frac{\vert{}R_t\vert{}}{P_t \times Q_t}$$

* **Where:**
* $\vert{}R_t\vert{}$ = Absolute daily return on day $t$.
* $P_t \times Q_t$ = Total dollar volume traded on day $t$.


* **Interpretation:** A higher $ILLIQ$ score means a small dollar order moves the stock price substantially. Controlled/low-float stocks naturally exhibit elevated $ILLIQ$ values during periods of unexpected order flow.

---

### 4. Overhang & Days-to-Absorb Ratio

Quantifies the downside supply risk if a major insider or holding company decides to liquidate a fraction of their position:

$$\text{Days to Absorb} = \frac{\text{Shares to be Liquidated}}{\text{ADV} \times \alpha}$$

* **Where $\alpha$** is the maximum acceptable market participation rate (typically $10\%\text{--}20\%$ of daily volume to avoid breaking the market).
* **Application:** If a 70% owner unloads even 5% of the total company, dividing that block by the float's normal daily volume reveals how many weeks or months of heavy selling pressure the public market must absorb.

---

### 5. Ownership Concentration (Herfindahl-Hirschman Index - HHI)

Measures voting and ownership concentration across all major holders ($s_i = \text{ownership percentage of holder } i$):

$$HHI = \sum_{i=1}^{n} s_i^2$$

* **Scale:** Ranges from near $0$ (widely dispersed public ownership) to $10,000$ (single 100% owner).
* **For TRI:** Woodbridge's $70\%$ stake alone yields $70^2 = 4,900$, placing it in the **highly concentrated** governance risk category ($HHI > 2,500$).

---