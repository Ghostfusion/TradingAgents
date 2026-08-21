**Discounted Cash Flow (DCF)** is a valuation methodology based on the principle of the **Time Value of Money (TVM)**: *a dollar received in the future is worth less than a dollar today* because a dollar today can be invested to earn a return.

In corporate finance and equity research, a DCF model states that **the intrinsic value of any business is the sum of all future cash flows it will generate, discounted back to today’s present value**.

---

## 1. The Core Mathematical Formula

In an **Unlevered DCF** (the most standard Wall Street methodology), valuation is split into two phases: the **explicit forecast period** (usually 5 to 10 years) and the **Terminal Value** (all cash flows beyond year $n$ into perpetuity).

$$\text{Enterprise Value (EV)} = \sum_{t=1}^{n} \frac{\text{FCFF}_t}{(1 + \text{WACC})^t} + \frac{\text{Terminal Value}_n}{(1 + \text{WACC})^n}$$

Where:

* $\text{FCFF}_t$: Free Cash Flow to Firm in period $t$.
* $\text{WACC}$: Weighted Average Cost of Capital (the discount rate).
* $\text{Terminal Value}_n$: Residual value of the company at the end of the forecast period.
* $n$: Number of years in the discrete forecast period.

---

## 2. The Core Building Blocks

### A. Free Cash Flow to Firm (FCFF / Unlevered FCF)

FCFF represents the actual operating cash available to all capital providers (debt and equity holders) after funding necessary operations and capital expenditures.

$$\text{FCFF} = \text{EBIT} \times (1 - \text{Tax Rate}) + \text{D\&A} - \Delta\text{NWC} - \text{CapEx}$$

* **$\text{EBIT}(1 - T)$ (NOPAT)**: Net Operating Profit After Taxes (operating income without considering capital structure/interest expense).
* **$\text{D\&A}$**: Depreciation & Amortization (added back because it is a non-cash expense).
* **$\Delta\text{NWC}$**: Change in Net Working Capital ($\text{Current Operating Assets} - \text{Current Operating Liabilities}$). An increase in working capital drains cash.
* **$\text{CapEx}$**: Capital Expenditures (cash spent on property, plant, equipment, or intangible assets to sustain and grow operations).

---

### B. The Discount Rate: Weighted Average Cost of Capital (WACC)

WACC reflects the required rate of return weighted proportionally by the firm's capital structure (Equity vs. Debt):

$$\text{WACC} = \left(\frac{E}{V} \times r_e\right) + \left(\frac{D}{V} \times r_d \times (1 - T)\right)$$

* $E$: Market Value of Equity
* $D$: Market Value of Debt
* $V$: Total Enterprise Value ($E + D$)
* $r_d$: Pre-tax Cost of Debt (effective yield on the company's bonds/loans)
* $T$: Marginal corporate tax rate (interest payments are tax-deductible)
* $r_e$: **Cost of Equity**, derived via the **Capital Asset Pricing Model (CAPM)**:

$$r_e = R_f + \beta \times (\text{ERP})$$

* **$R_f$ (Risk-Free Rate)**: Yield on benchmark long-term government bonds (e.g., 10-year or 30-year US Treasury yield).
* **$\beta$ (Beta)**: Measure of the stock’s volatility/systematic risk relative to the broader market ($\beta > 1$ means more volatile than the index).
* **$\text{ERP}$ (Equity Risk Premium)**: The expected excess return demanded by investors over the risk-free rate ($R_m - R_f$, typically 4.5%–6.0%).

---

### C. Terminal Value (TV)

Since businesses operate as going concerns indefinitely, typically **60% to 85% of total enterprise value** comes from the Terminal Value. There are two primary methods to estimate it:

#### 1. Perpetuity Growth Method (Gordon Growth Model)

Assumes the company grows at a stable, sustainable rate $g$ forever (where $g$ is usually set below or equal to long-term GDP growth, ~2%–3%).

$$\text{Terminal Value}_n = \frac{\text{FCFF}_{n} \times (1 + g)}{\text{WACC} - g}$$

#### 2. Exit Multiple Method

Assumes the company is sold at year $n$ at a valuation multiple benchmarked to industry peers (e.g., Enterprise Value / EBITDA).

$$\text{Terminal Value}_n = \text{EBITDA}_n \times (\text{Industry EV/EBITDA Multiple})$$

---

## 3. Step-by-Step Valuation Workflow

```
[ Financial Statements ]
          │
          ▼
1. Forecast P&L & Balance Sheet (5-10 Years)
          │
          ▼
2. Calculate Projected FCFF for Years 1..N
          │
          ▼
3. Determine Discount Rate (WACC via CAPM)
          │
          ▼
4. Calculate Terminal Value at Year N
          │
          ▼
5. Discount FCFF & TV to Present Value (PV) ──► Sum = Enterprise Value (EV)
          │
          ▼
6. Bridge EV to Equity Value (EV + Cash - Total Debt)
          │
          ▼
7. Divide by Diluted Shares Outstanding ──► Fair Value per Share

```

### From Enterprise Value to Per-Share Equity Value:

Once you have the total Enterprise Value:


$$\text{Equity Value} = \text{Enterprise Value} + \text{Cash \& Equivalents} - \text{Total Debt} - \text{Minority Interests} - \text{Preferred Stock}$$

$$\text{Target Price per Share} = \frac{\text{Equity Value}}{\text{Diluted Shares Outstanding}}$$

---

## 4. Concrete Numerical Walkthrough

Let’s value a hypothetical technology company with the following assumptions:

| Parameter | Value |
| --- | --- |
| **Current Shares Outstanding** | 100 million |
| **Cash on Balance Sheet** | $200 million |
| **Total Debt** | $100 million |
| **WACC ($r$)** | 10.0% |
| **Long-term Growth Rate ($g$)** | 2.5% |

### Projected Free Cash Flows ($ Millions)

| Year | Year 1 | Year 2 | Year 3 | Year 4 | Year 5 |
| --- | --- | --- | --- | --- | --- |
| **FCFF** | $100.0 | $115.0 | $130.0 | $145.0 | $160.0 |
| **Discount Factor $\frac{1}{(1.10)^t}$** | 0.9091 | 0.8264 | 0.7513 | 0.6830 | 0.6209 |
| **Present Value (PV)** | **$90.91** | **$95.04** | **$97.67** | **$99.04** | **$99.34** |

* **Sum of 5-Year Explicit PV(FCFF)** = **$482.00M**

### Calculating Terminal Value

$$\text{TV}_5 = \frac{\$160.0 \times (1 + 0.025)}{0.10 - 0.025} = \frac{\$164.0}{0.075} = \$2,186.67\text{M}$$

$$\text{PV}(\text{TV}) = \frac{\$2,186.67}{(1.10)^5} = \$2,186.67 \times 0.6209 = \mathbf{\$1,357.70M}$$

### Bridging to Equity Value & Stock Price

* **Enterprise Value**: $\$482.00\text{M} + \$1,357.70\text{M} = \mathbf{\$1,839.70\text{M}}$
* **Equity Value**: $\$1,839.70\text{M} + \$200\text{M (Cash)} - \$100\text{M (Debt)} = \mathbf{\$1,939.70\text{M}}$
* **Fair Value Per Share**: $\frac{\$1,939.70\text{M}}{100\text{M shares}} = \mathbf{\$19.40 / \text{share}}$

---

## 5. Why Interest Rates Heavily Impact Tech/Growth Stocks

In the DCF framework, the sensitivity to interest rates depends heavily on **cash flow duration**:

```
Value Contribution Over Time:

Mature Cash Cow (Short Duration):
[==== Year 1-5 (High PV) ====] [== Terminal Value ==]  -> Less sensitive to 'r'

High-Growth Tech (Long Duration):
[= Y1-5 (Near 0 or Negative) =] [================= Terminal Value =================]  -> Highly sensitive to 'r'

```

1. **The Math of the Denominator**: The Risk-Free Rate ($R_f$) feeds directly into CAPM $\rightarrow$ WACC. When the 10Y/30Y Treasury yield climbs, the discount rate $r$ increases.
2. **Compound Compressing Effect**: For cash flows expected 10–20 years out, the term $(1 + r)^t$ scales exponentially with $t$. A 100 bps (1%) increase in WACC cuts the present value of cash flows in Year 15 far more drastically than cash flows in Year 1.
3. **Double Squeeze on Terminal Value**: The Gordon Growth denominator is $(\text{WACC} - g)$. If WACC increases from 8% to 10% with $g = 3\%$, the denominator jumps from $5\%$ to $7\%$—a **$28.5\%$ drop in Terminal Value** before discounting.

---

## 6. Key Strengths & Limitations

| Strengths | Limitations |
| --- | --- |
| **Intrinsic Focus**: Measures fundamental cash generation rather than market sentiment or noisy accounting metrics (e.g., EBITDA/EPS). | **High Sensitivity ("GIGO")**: Small changes in WACC (±0.5%) or growth rates ($g$) yield wildly diverging price targets. |
| **Capital Structure Neutral**: Unlevered DCF evaluates operations independently of debt financing decisions. | **Terminal Value Dominance**: A huge percentage of final value relies on assumptions made 5–10 years into the future. |
| **Customizable**: Handles complex scenarios like capital investment cycles, operating leverage, and margin expansions. | **Weak for Early-Stage Companies**: Highly unreliable for companies with negative operating cash flows or unpredictable business models. |

---

## 7. Sensitivity Analysis (Stress-Testing Assumptions)

Because no single DCF point estimate is certain, analysts always present a **Sensitivity Matrix** showing how the stock price shifts across combinations of **WACC** and **Terminal Growth Rate ($g$)**:

| WACC \ $g$ | 2.0% | 2.5% (Base) | 3.0% |
| --- | --- | --- | --- |
| **9.0%** | $21.45 | $22.68 | $24.15 |
| **10.0% (Base)** | $18.48 | **$19.40** | $20.48 |
| **11.0%** | $16.19 | $16.89 | $17.69 |

A 100 bps shift in discount rate causes roughly a **13% swing** in the equity value of the company in this model.