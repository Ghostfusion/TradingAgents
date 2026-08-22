For **Mega-Cap Tech** on a **1 to 4 week swing horizon** with **tranche scale-in execution**, the math balances valuation support, volatility-based tranche spacing, and strict 1.0%–2.0% total portfolio risk.

---

### 1. Tranche Spacing & Scale-In Sizing

Mega-cap tech dips often form multi-leg bottoms or undercut prior support before reversing. A **3-tranche scale-in model** (e.g., 30% / 30% / 40% or 25% / 35% / 40%) anchors entries across key volatility boundaries.

* **Tranche Price Triggers (ATR/Support Spacing):**

$$P_1 = P_{\text{initial signal}} \quad (\text{e.g., RSI}(14) \le 35 \text{ or first test of 50-day EMA})$$


$$P_2 = P_1 - (1.0 \times \text{ATR}_{14})$$


$$P_3 = P_1 - (2.0 \times \text{ATR}_{14}) \quad (\text{or major weekly support / 200-day SMA})$$


* **Total Position Size Constraint ($N_{\text{total}}$ Shares):**

$$N_{\text{total}} = \frac{\text{Account Size} \times \text{Max Risk \%}}{\bar{P}_{\text{entry}} - \text{Stop Loss}}$$


* $\bar{P}_{\text{entry}} = \sum (w_i \times P_i)$, where $w_i$ is the weight of tranche $i$ ($\sum w_i = 1.0$).
* $N_i = w_i \times N_{\text{total}}$



---

### 2. Hard Stop & Volatility Invalidation

For mega-cap tech swings, the invalidation level sits beneath the final scale-in tier:

* **Composite Stop Loss:**

$$\text{Stop Loss} = P_3 - (1.0\text{ to }1.5 \times \text{ATR}_{14})$$


* **Total Capital at Risk ($\$$):**

$$\text{Risk}_{\$} = \sum_{i=1}^{k} N_i \times (P_i - \text{Stop Loss}) \le \text{Account Size} \times \text{Risk \%} \quad (1.0\%\text{--}2.0\%)$$



---

### 3. Intermediate Profit Targets (1–4 Week Horizon)

Mega-cap swings typically exhaust near declining moving averages or upper volatility envelopes:

* **Target 1 (Mean Reversion - 50% Size):** 20-day EMA or middle Bollinger Band ($R:R \ge 1.8$).
* **Target 2 (Momentum Extension - 50% Size):** Prior breakdown pivot or $+2\sigma$ Upper Bollinger Band ($R:R \ge 3.0$).
* **Blended Trade Expectancy:**

$$R_{\text{blended}} = (0.5 \times R_1) + (0.5 \times R_2)$$



---

### 4. Interactive Payoff & Risk Simulation (sample code only for reference)

Here is a standalone, interactive Python application using **Streamlit** and **Plotly** that models the complete Value Dip + Swing Trading tranche scale-in, risk invalidation, and profit target trajectory.

### Prerequisites

Install the required packages:

```bash
pip install streamlit plotly numpy pandas

```

### Python Code (`app.py`)

```python
import streamlit as st
import numpy as np
import pandas as pd
import plotly.graph_objects as go

st.set_page_config(page_title="Value Dip Swing Trader", layout="wide")

st.title("📈 Value Dip + Swing Scale-In Simulator")
st.caption("Intermediate (1-4 Week) Mega-Cap Tech Swing Trading Risk & Payoff Engine")

# --- Sidebar Inputs ---
st.sidebar.header("1. Account & Risk Parameters")
account_size = st.sidebar.number_input("Account Size ($)", value=100000, step=5000, min_value=1000)
risk_pct = st.sidebar.slider("Max Account Risk (%)", min_value=0.5, max_value=3.0, value=1.5, step=0.25)
max_dollar_risk = account_size * (risk_pct / 100.0)

st.sidebar.header("2. Asset & Volatility Setup")
p1 = st.sidebar.number_input("Initial Entry Price / P1 ($)", value=180.0, step=1.0)
atr_14 = st.sidebar.number_input("14-Day ATR ($)", value=4.50, step=0.25)
holding_days = st.sidebar.slider("Trade Horizon (Trading Days)", min_value=5, max_value=30, value=20)

st.sidebar.header("3. Tranche Weights")
w1 = st.sidebar.slider("Tranche 1 Weight (%)", min_value=10, max_value=60, value=30, step=5) / 100.0
w2 = st.sidebar.slider("Tranche 2 Weight (%)", min_value=10, max_value=60, value=30, step=5) / 100.0
w3 = 1.0 - (w1 + w2)
st.sidebar.write(f"**Tranche 3 Weight:** {w3*100:.0f}%")

if w3 < 0:
    st.sidebar.error("Weights must sum to 100%! Adjust Tranche 1 and 2.")
    st.stop()

# --- Trade Calculations ---
# Tranche Price Triggers
p2 = p1 - (1.0 * atr_14)
p3 = p1 - (2.0 * atr_14)

# Invalidation Stop (1.5x ATR below final tranche)
stop_loss = p3 - (1.5 * atr_14)

# Weighted Average Entry Price
avg_entry = (w1 * p1) + (w2 * p2) + (w3 * p3)
risk_per_share = avg_entry - stop_loss

# Sizing
total_shares = int(max_dollar_risk / risk_per_share)
n1 = int(total_shares * w1)
n2 = int(total_shares * w2)
n3 = total_shares - (n1 + n2)

total_allocated_capital = total_shares * avg_entry

# Targets
target_1 = avg_entry + (1.8 * risk_per_share)  # R:R = 1.8 (Mean Reversion / 20 EMA)
target_2 = avg_entry + (3.0 * risk_per_share)  # R:R = 3.0 (Momentum Extension)
blended_target = (0.5 * target_1) + (0.5 * target_2)

expected_dollar_gain = (0.5 * total_shares * (target_1 - avg_entry)) + (0.5 * total_shares * (target_2 - avg_entry))
realized_rr = expected_dollar_gain / max_dollar_risk

# --- Summary KPI Metrics ---
col1, col2, col3, col4 = st.columns(4)
col1.metric("Max Dollar Risk", f"${max_dollar_risk:,.2f}", f"{risk_pct}% of Account")
col2.metric("Total Position Capital", f"${total_allocated_capital:,.2f}", f"{total_shares} Shares")
col3.metric("Weighted Avg Entry", f"${avg_entry:.2f}", f"Stop: ${stop_loss:.2f}")
col4.metric("Target Expectancy (R:R)", f"{realized_rr:.2f}R", f"+${expected_dollar_gain:,.2f}")

# --- Tranche Breakdown Table ---
st.subheader("Scale-In Tranche Specification")
tranche_df = pd.DataFrame({
    "Tranche": ["Tranche 1 (Signal)", "Tranche 2 (-1.0 ATR)", "Tranche 3 (-2.0 ATR)", "Hard Invalidation"],
    "Trigger Price": [f"${p1:.2f}", f"${p2:.2f}", f"${p3:.2f}", f"${stop_loss:.2f}"],
    "Weight": [f"{w1*100:.0f}%", f"{w2*100:.0f}%", f"{w3*100:.0f}%", "-"],
    "Shares Allocated": [n1, n2, n3, total_shares],
    "Capital Required": [f"${n1*p1:,.2f}", f"${n2*p2:,.2f}", f"${n3*p3:,.2f}", f"${total_allocated_capital:,.2f}"]
})
st.dataframe(tranche_df, use_container_width=True, hide_index=True)

# --- Simulation Curve Plot ---
st.subheader("Trade Path Simulation & Payoff Trajectory")
days_axis = np.linspace(0, holding_days, 100)

# Theoretical price path: dip completion -> harmonic mean reversion -> target expansion
swing_price_curve = avg_entry + (blended_target - avg_entry) * np.sin((days_axis / holding_days) * (np.pi / 2))
position_value_curve = swing_price_curve * total_shares
stop_value_floor = np.full_like(days_axis, stop_loss * total_shares)
target_value_ceiling = np.full_like(days_axis, blended_target * total_shares)

fig = go.Figure()

# Trajectory Curve
fig.add_trace(go.Scatter(
    x=days_axis, y=position_value_curve,
    mode='lines', name='Projected Swing Value',
    line=dict(color='#2962FF', width=3)
))

# Target Level
fig.add_trace(go.Scatter(
    x=days_axis, y=target_value_ceiling,
    mode='lines', name='Blended Target (1.8R - 3.0R)',
    line=dict(color='#00C853', width=2, dash='dash')
))

# Stop Level
fig.add_trace(go.Scatter(
    x=days_axis, y=stop_value_floor,
    mode='lines', name='Invalidation Floor (Stop Loss)',
    line=dict(color='#D50000', width=2, dash='dot')
))

fig.update_layout(
    xaxis_title="Trading Days Elapsed",
    yaxis_title="Total Position Equity ($)",
    hovermode="x unified",
    margin=dict(l=20, r=20, t=30, b=20),
    template="plotly_white"
)

st.plotly_chart(fig, use_container_width=True)