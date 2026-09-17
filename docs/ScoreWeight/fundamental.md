The **106-factor table** I referred to is the **Fundamental Factor Weight Master Table** we built for your quant application's fundamental-analysis engine.

It is a catalog of **106 individual fundamental formulas/factors**, organized into 10 categories, with an initial proposed weight for each factor. The weights were **starting research weights, not empirically validated weights**.

### The 10 categories

| #  | Fundamental category          |   Weight |
| -- | ----------------------------- | -------: |
| 1  | Profitability / Quality       |  **18%** |
| 2  | Growth                        |  **15%** |
| 3  | Cash Flow                     |  **17%** |
| 4  | Valuation                     |  **20%** |
| 5  | Balance Sheet                 |  **10%** |
| 6  | Earnings / Accounting Quality |   **8%** |
| 7  | Capital Efficiency            |   **4%** |
| 8  | Capital Returns               |   **4%** |
| 9  | Distress / Financial Risk     |   **2%** |
| 10 | Insider Activity              |   **2%** |
|    | **Total**                     | **100%** |

### The 106 factors

**Profitability / Quality — 18%**

1. ROIC — 3.0%
2. ROE — 2.0%
3. ROA — 1.5%
4. Gross Profit / Assets — 2.5%
5. Operating Margin — 2.0%
6. Gross Margin — 1.5%
7. EBITDA Margin — 1.0%
8. EBIT Margin — 1.0%
9. FCF Margin — 1.5%
10. Operating Margin Stability — 1.0%
11. Gross Margin Stability — 0.5%
12. ROIC Stability — 0.5%

**Growth — 15%**
13. Revenue Growth YoY — 2.0%
14. Revenue CAGR 3Y — 1.5%
15. Revenue CAGR 5Y — 1.0%
16. EPS Growth YoY — 1.5%
17. EPS CAGR 3Y — 1.0%
18. EPS CAGR 5Y — 0.75%
19. FCF Growth YoY — 1.5%
20. FCF CAGR 3Y — 1.25%
21. EBITDA Growth — 0.75%
22. EBIT Growth — 0.75%
23. Operating Income CAGR — 0.75%
24. Margin Expansion — 1.0%
25. FCF Margin Expansion — 0.75%
26. Growth Quality = FCF Growth / EPS Growth — 0.75%

**Cash Flow — 17%**
27. FCF Yield — 3.0%
28. OCF Yield — 1.0%
29. FCF Margin — 1.5%
30. OCF Margin — 1.0%
31. FCF Conversion = FCF / Net Income — 2.0%
32. CFO Conversion = OCF / Net Income — 1.0%
33. FCF / EBITDA — 1.0%
34. OCF / EBITDA — 0.5%
35. CapEx / Revenue — 1.0%
36. CapEx / OCF — 1.0%
37. FCF Stability — 1.0%
38. FCF CAGR 5Y — 1.0%
39. Cash Conversion Stability — 0.5%
40. Accrual-adjusted FCF — 0.5%
41. Maintenance CapEx FCF — 1.0%
42. Normalized FCF Yield — 2.0%

**Valuation — 20%**
43. P/E — 2.0%
44. Forward P/E — 1.5%
45. PEG — 1.5%
46. EV/EBIT — 2.0%
47. EV/EBITDA — 1.5%
48. EV/Sales — 0.75%
49. P/S — 0.75%
50. P/B — 0.75%
51. P/CF — 1.0%
52. Price/FCF — 1.5%
53. FCF Yield — 2.0%
54. Earnings Yield — 1.0%
55. EV/FCF — 1.0%
56. DCF Upside — 1.5%
57. Normalized DCF Upside — 1.5%
58. PEG-adjusted FCF — 0.5%
59. EV/FCF Growth — 0.5%

**Balance Sheet — 10%**
60. Net Debt / EBITDA — 1.5%
61. Debt / Equity — 1.0%
62. Debt / Assets — 0.75%
63. Net Debt / FCF — 1.0%
64. Interest Coverage — 1.0%
65. Current Ratio — 0.75%
66. Quick Ratio — 0.5%
67. Cash / Debt — 1.0%
68. Net Cash Yield — 0.5%
69. Working Capital / Assets — 0.5%
70. Debt Growth — 0.5%
71. Debt Service Capacity = OCF / Debt — 1.0%

**Earnings / Accounting Quality — 8%**
72. Piotroski F-Score — 1.25%
73. Beneish M-Score — 1.0%
74. Accrual Ratio — 1.25%
75. CFO − Net Income — 0.75%
76. Asset Growth — 0.5%
77. Receivables Growth vs Revenue — 0.75%
78. Inventory Growth vs Revenue — 0.5%
79. Deferred Revenue Growth — 0.5%
80. Earnings Volatility — 0.5%
81. OCF/NI Divergence — 0.5%
82. Quality of Earnings — 1.0%

**Capital Efficiency — 4%**
83. Asset Turnover — 0.75%
84. Invested Capital Turnover — 0.75%
85. Capital Turnover — 0.5%
86. Incremental ROIC — 1.0%
87. Incremental Asset Efficiency — 0.5%
88. NOA / Sales — 0.5%

**Capital Returns — 4%**
89. Dividend Yield — 0.5%
90. Dividend Growth — 0.5%
91. Payout Ratio — 0.5%
92. Buyback Yield — 1.0%
93. Share Count Growth — 0.75%
94. Total Shareholder Yield — 0.75%

**Distress / Financial Risk — 2%**
95. Altman Z-Score — 0.50%
96. Ohlson O-Score — 0.40%
97. Distance to Default — 0.40%
98. Interest Coverage Stress — 0.25%
99. Liquidity Stress — 0.20%
100. Debt Maturity Risk — 0.25%

**Insider Activity — 2%**
101. Net Insider Buying — 0.50%
102. Insider Buy/Sell Ratio — 0.40%
103. Open-Market Insider Buying — 0.50%
104. Insider Selling Acceleration — 0.25%
105. Executive Participation — 0.20%
106. Insider Ownership Change — 0.15%

### But there is an important correction to how we should use it

Given your **Q1–Q5 decisions**, I would now treat this table as a **factor catalog + deterministic baseline**, not as an established truth.

In other words:

```text
106 Fundamental Factors
        ↓
normalize each factor
        ↓
remove/penalize redundancy
        ↓
apply sector applicability
        ↓
apply data-quality adjustment
        ↓
deterministic baseline weights
        ↓
FundamentalScore (0–100)
        ↓
ADVISORY
```

Then Phase C/4 tests whether those factors actually have predictive value:

```text
106 factors
    ↓
Full EODHD US universe
    ↓
Walk-forward IC / Rank IC
    ↓
Decile spread
    ↓
Monotonicity
    ↓
IC stability
    ↓
Redundancy
    ↓
Sector robustness
    ↓
Possible learned weights
```

So **106 does not mean your system has proven that 106 independent pieces of information exist**. In fact, there is substantial overlap—for example, FCF Yield, Price/FCF, Normalized FCF Yield, Earnings Yield, and several profitability/cash-flow measures.

That's exactly why your earlier question about **how to rank formula weights empirically** is important. The 106-factor table is the **starting inventory**; the eventual empirical testing should determine which factors deserve meaningful weight.
