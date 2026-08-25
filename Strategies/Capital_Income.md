**Underlying Benchmark:** Global X U.S. High Yield Preferred Index (Solactive AG)

**Universe:** US-listed preferred stocks, hybrid capital instruments, and depository preferred shares.

#### **Mathematical Methodology**

1. **Liquidity & Quality Screen:**
* Market Capitalization: $\text{Market Cap} \ge \$250\text{M}$ (or $\ge \$100\text{M}$ for existing components).
* 3-Month Average Daily Turnover ($\text{ADTV}$): $\text{ADTV} \ge \$1\text{M}$.


2. **Yield Metric Calculation & Selection:**
Each eligible preferred security is evaluated on its **Indicated Dividend Yield ($Y_i$)**:

$$Y_i = \frac{D_{\text{annualized}, i}}{P_{i}}$$



*where $D_{\text{annualized}, i}$ is the latest declared dividend annualized, and $P_i$ is the current spot price.*
* **Selection:** The top 50 highest-yielding preferred securities are selected into the index.


3. **Weighting and Capping Optimization:**
The initial weight is market-value-weighted based on outstanding preferred issue size ($MV_i$):

$$w_{i, \text{raw}} = \frac{MV_i}{\sum_{j=1}^{50} MV_j}$$



A mandatory single-constituent cap of **3.0%** (maximum 3.5%) is applied at semi-annual rebalances:

$$w_i = \begin{cases} 3.0\%, & \text{if } w_{i, \text{raw}} \ge 3.0\% \\ w_{i, \text{raw}} + \Delta_i, & \text{if } w_{i, \text{raw}} < 3.0\% \end{cases}$$



*where $\Delta_i$ represents the pro-rata redistribution of excess weight from capped securities.*

