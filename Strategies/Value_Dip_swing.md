A **Value Dip + Swing Trading Hybrid** framework combines fundamental valuation triggers (to establish high-probability, discounted entries) with technical momentum and risk mechanics (to capture intermediate price expansions).

---

### 1. Value Dip Identification (Valuation & Discount)

These calculations ensure you are buying fundamentally sound assets at a margin of safety rather than catching a falling knife.

* **Margin of Safety (Intrinsic Value Discount):**

$$\text{Margin of Safety (\%)} = \frac{\text{Intrinsic Value} - \text{Current Price}}{\text{Intrinsic Value}} \times 100$$



*Used to verify that the entry price reflects an adequate discount (e.g., $\ge 15\text{--}25\%$).*
* **Historical Valuation Deviation ($Z\text{-Score}$ of Multiples):**

$$Z = \frac{\text{Multiple}_{\text{current}} - \mu_{\text{historical}}}{\sigma_{\text{historical}}}$$



*Where multiple can be P/E, EV/EBITDA, or P/FCF. A $Z \le -1.5$ indicates the asset is trading significantly below its historical norm.*
* **Free Cash Flow Yield:**

$$\text{FCF Yield} = \frac{\text{Free Cash Flow}}{\text{Market Capitalization}} \times 100$$



*Provides a baseline yield to guard against terminal risk during extended consolidations.*

---

### 2. Technical Dip Confirmation (Mean Reversion & Volatility)

These metrics determine whether the dip is oversold and beginning to stabilize for a swing.

* **Relative Strength Index (RSI - 14 Period):**

$$\text{RSI} = 100 - \left( \frac{100}{1 + \text{RS}} \right), \quad \text{RS} = \frac{\text{Average Gain}}{\text{Average Loss}}$$



*Oversold conditions ($\text{RSI} \le 30\text{--}35$) paired with bullish divergence signal entry zones.*
* **Bollinger Band Percentile (%b):**

$$\%b = \frac{\text{Current Price} - \text{Lower Band}}{\text{Upper Band} - \text{Lower Band}}$$



*$\%b \le 0$ signals price is piercing the lower 2-standard-deviation band.*
* **Average True Range (ATR Trailing Volatility):**

$$\text{TR} = \max\big[(\text{High} - \text{Low}), \vert{}\text{High} - \text{Close}_{\text{prev}}\vert{}, \vert{}\text{Low} - \text{Close}_{\text{prev}}\vert{}\big]$$


$$\text{ATR}_{n} = \frac{\text{ATR}_{n-1} \times (n-1) + \text{TR}_n}{n}$$



*Defines market noise to set volatility-adjusted stops.*

---

### 3. Execution, Risk Management & Sizing

Essential formulas to protect capital while scaling into multi-day or multi-week swings.

* **Fixed Fractional Position Sizing:**

$$\text{Shares} = \frac{\text{Account Size} \times \text{Risk Per Trade (\%)}}{\text{Entry Price} - \text{Stop Loss}}$$


* **Volatility-Based Stop Loss:**

$$\text{Stop Loss} = \text{Entry Price} - (k \times \text{ATR}_{14}) \quad (k \in [1.5, 2.5])$$


* **Risk-to-Reward Ratio ($R:R$):**

$$R:R = \frac{\text{Target Exit} - \text{Entry Price}}{\text{Entry Price} - \text{Stop Loss}}$$



*Hybrid setups typically target $\ge 2:1$ or $3:1$.*
* **Weighted Average Entry (Dip Scaling / Tranching):**

$$\bar{P}_{\text{entry}} = \frac{\sum (P_i \times Q_i)}{\sum Q_i}$$



---

### 4. Swing Trade Profit & Portfolio Expectancy

* **Breakeven Win Rate:**

$$\text{Breakeven Rate} = \frac{1}{1 + R:R}$$


* **Mathematical Expectancy per Trade:**

$$E = (P_{\text{win}} \times W) - (P_{\text{loss}} \times L)$$



*Where $P$ is probability and $W/L$ are average win/loss amounts.*
* **Hybrid Swing Allocation Matrix:**

| Dimension | Primary Metric | Target Threshold | Purpose |
| --- | --- | --- | --- |
| **Value Floor** | Margin of Safety / FCF Yield | $\ge 20\%$ discount / $\ge 6\%$ FCF | Protects downside if swing trade extends |
| **Technical Entry** | RSI(14) + Lower Bollinger | $\text{RSI} \le 35$ & $\%b \le 0.10$ | Optimizes mean-reversion timing |
| **Trade Risk** | Fixed Fraction + ATR Stop | $\le 1\text{--}2\%$ account risk; $2 \times \text{ATR}$ | Controls drawdowns on structural breaks |
| **Exit Target** | Mean Reversion (EMA 20/50) | $R:R \ge 2.5$ | Captures cyclical expansion |

---