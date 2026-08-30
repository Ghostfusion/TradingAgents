The Python script below uses Alpha Vantage's `NEWS_SENTIMENT` API and `pandas` to fetch article feeds, parse ticker-specific sentiment scores, aggregate them into daily averages, and calculate a 7-day rolling moving average.

### Python Script

```python
import os
import requests
import pandas as pd

def fetch_ticker_sentiment_history(ticker: str, api_key: str, limit: int = 200) -> pd.DataFrame:
    """
    Fetches news sentiment from Alpha Vantage for a specific ticker
    and computes the daily average and 7-day Simple Moving Average (SMA).
    """
    url = "https://www.alphavantage.co/query"
    params = {
        "function": "NEWS_SENTIMENT",
        "tickers": ticker,
        "limit": limit,
        "apikey": api_key
    }

    response = requests.get(url, params=params, timeout=15)
    response.raise_for_status()
    data = response.json()

    if "feed" not in data:
        error_msg = data.get("Note") or data.get("Error Message") or "No feed returned."
        raise ValueError(f"API Error: {error_msg}")

    records = []
    for item in data["feed"]:
        # Parse timestamp: Format is YYYYMMDDTHHMMSS
        dt = pd.to_datetime(item["time_published"], format="%Y%m%dT%H%M%S")
        
        # Locate the specific sentiment score for the targeted ticker
        ticker_score = None
        for t in item.get("ticker_sentiment", []):
            if t.get("ticker") == ticker.upper():
                ticker_score = float(t.get("ticker_sentiment_score", 0.0))
                break
        
        # Fallback to overall sentiment score if ticker-specific score is absent
        if ticker_score is None:
            ticker_score = float(item.get("overall_sentiment_score", 0.0))

        records.append({"timestamp": dt, "sentiment_score": ticker_score})

    if not records:
        return pd.DataFrame()

    df = pd.DataFrame(records)
    df["date"] = df["timestamp"].dt.floor("D")

    # 1. Aggregate to daily mean score
    daily_sentiment = df.groupby("date")["sentiment_score"].mean().to_frame("daily_mean_sentiment")

    # 2. Reindex across a complete calendar date range to avoid gap distortion
    full_idx = pd.date_range(start=daily_sentiment.index.min(), end=daily_sentiment.index.max(), freq="D")
    daily_sentiment = daily_sentiment.reindex(full_idx)

    # 3. Compute 7-day rolling SMA (forward-fill or min_periods handles low-volume days)
    daily_sentiment["7d_sentiment_sma"] = (
        daily_sentiment["daily_mean_sentiment"]
        .rolling(window=7, min_periods=1)
        .mean()
    )

    return daily_sentiment

if __name__ == "__main__":
    API_KEY = os.getenv("ALPHAVANTAGE_API_KEY", "demo")
    TICKER = "AAPL"

    df_sentiment = fetch_ticker_sentiment_history(ticker=TICKER, api_key=API_KEY, limit=200)

    # Display the most recent 14 days
    print(df_sentiment.tail(14).to_string())

```

### Key Considerations

* **Ticker vs. Overall Sentiment:** Alpha Vantage delivers both an `overall_sentiment_score` (entire article context) and a `ticker_sentiment_score` (-1.0 to 1.0) paired with a relevance score (0.0 to 1.0). Filtering specifically for `ticker_sentiment_score` prevents market noise from multi-asset articles.
* **Date Continuity:** News volume varies drastically between trading days and weekends. Using `pd.date_range` ensures the 7-day rolling window represents actual 7 calendar days rather than the last 7 active news days.
* **Pagination & History Limits:** The default `NEWS_SENTIMENT` endpoint returns up to 200 items per call (up to 1,000 on premium tiers). For longer backtests, append `time_from=YYYYMMDDTHHMM` and `time_to=YYYYMMDDTHHMM` parameters in iterative requests.

To test whether news sentiment leads price action, correlate current sentiment against **future percentage returns** across multiple forward horizons (e.g., $t+1, t+2, \dots, t+k$ trading days) rather than raw price levels. Raw prices exhibit non-stationarity and unit-root trends that yield spurious correlation.

### Python Implementation

This script calculates forward returns for multiple lookahead shifts ($k \in [-10, +10]$), computes Pearson and Spearman rank correlations, calculates $p$-values via `scipy.stats`, and visualizes the lead/lag cross-correlation structure.

```python
import numpy as np
import pandas as pd
from scipy import stats
import plotly.graph_objects as go

def compute_sentiment_lead_lag(
    df: pd.DataFrame, 
    price_col: str = "close", 
    sentiment_col: str = "sentiment_7d_sma", 
    max_lags: int = 10
) -> pd.DataFrame:
    """
    Computes cross-correlation between sentiment_col and forward price returns.
    
    Positive lag (+k): Sentiment at t correlates with Returns at t+k (Sentiment LEADS).
    Negative lag (-k): Sentiment at t correlates with Returns at t-k (Price LEADS sentiment).
    Lag 0: Contemporaneous correlation.
    """
    # 1. Compute 1-day percentage returns: R_t = (P_t - P_{t-1}) / P_{t-1}
    df = df.copy().sort_index()
    df["daily_return"] = df[price_col].pct_change()

    results = []

    # Iterate through lags from -max_lags to +max_lags
    for lag in range(-max_lags, max_lags + 1):
        # Shift daily returns by -lag so return at t+lag aligns with sentiment at t
        # For lag > 0 (forward return): return_series is df["daily_return"].shift(-lag)
        shifted_return = df["daily_return"].shift(-lag)
        
        # Form pairwise dataset and drop NaNs
        aligned = pd.concat([df[sentiment_col], shifted_return], axis=1).dropna()
        aligned.columns = ["sentiment", "future_return"]

        if len(aligned) < 10:
            continue

        # Pearson (linear) & Spearman (monotonic/rank) correlation
        pearson_corr, pearson_pval = stats.pearsonr(aligned["sentiment"], aligned["future_return"])
        spearman_corr, spearman_pval = stats.spearmanr(aligned["sentiment"], aligned["future_return"])

        results.append({
            "lag_days": lag,
            "pearson_corr": pearson_corr,
            "pearson_pval": pearson_pval,
            "spearman_corr": spearman_corr,
            "spearman_pval": spearman_pval,
            "sample_size": len(aligned)
        })

    return pd.DataFrame(results)

def plot_cross_correlation(corr_df: pd.DataFrame, ticker: str):
    fig = go.Figure()

    # Bar chart for Pearson Correlation
    colors = ["#2ca02c" if p < 0.05 else "#aec7e8" for p in corr_df["pearson_pval"]]

    fig.add_trace(go.Bar(
        x=corr_df["lag_days"],
        y=corr_df["pearson_corr"],
        marker_color=colors,
        text=[f"p={p:.3f}" for p in corr_df["pearson_pval"]],
        textposition="auto",
        name="Pearson Correlation"
    ))

    # Significance boundary reference lines (approx. 95% CI: +/- 1.96 / sqrt(N))
    avg_n = corr_df["sample_size"].mean()
    ci_bound = 1.96 / np.sqrt(avg_n)

    fig.add_hline(y=ci_bound, line_dash="dot", line_color="red", annotation_text="+95% CI")
    fig.add_hline(y=-ci_bound, line_dash="dot", line_color="red", annotation_text="-95% CI")
    fig.add_vline(x=0, line_dash="solid", line_color="gray")

    fig.update_layout(
        title=f"{ticker} — Sentiment Lead/Lag Cross-Correlation Profile",
        xaxis_title="Lag in Trading Days (Positive = Sentiment Leads Price)",
        yaxis_title="Correlation Coefficient",
        template="plotly_white",
        bargap=0.25
    )

    fig.show()

# Example execution using merged_df from previous step
if __name__ == "__main__":
    # Assuming 'merged_df' contains 'close' and 'sentiment_7d_sma'
    # corr_results = compute_sentiment_lead_lag(merged_df, max_lags=10)
    # print(corr_results.to_string(index=False))
    # plot_cross_correlation(corr_results, ticker="AAPL")
    pass

```

### How to Interpret the Lag Profile

| Lag Value ($k$) | Alignment | Economic Interpretation |
| --- | --- | --- |
| **$k > 0$ (e.g., $+1, +3$)** | Sentiment at $t$ vs. Return at $t+k$ | **Sentiment Leads:** Today's news sentiment has predictive power over future price changes over the next $k$ trading days. |
| **$k = 0$** | Sentiment at $t$ vs. Return at $t$ | **Contemporaneous:** News and price adjust simultaneously on the same trading day (efficient absorption). |
| **$k < 0$ (e.g., $-1, -3$)** | Sentiment at $t$ vs. Return at $t-k$ | **Price Leads:** Media reports and sentiment react to price moves that already occurred (retroactive media coverage). |

### Important Modeling Caveats

* **Autocorrelation Distortion:** A 7-day rolling SMA introduces artificial auto-correlation into the sentiment series. To test pure novelty/shock, compare results using **raw daily sentiment innovations** (e.g., $\text{Score}_t - \text{Score}_{t-1}$) alongside the SMA.
* **Lookahead Bias:** Ensure that daily news sentiment timestamps exclusively cover articles published *prior* to the market close of day $t$ when matching against return $R_{t+1}$. If post-market articles are included in day $t$, filter them to avoid lookahead contamination.

To evaluate predictive power across multiple investment horizons, we estimate the multi-horizon predictive regression:

$$R_{t \to t+h} = \alpha_h + \beta_{1,h} \text{Sent}_t + \beta_{2,h} R_{t-1} + \beta_{3,h} \Delta \ln(\text{Vol}_t) + \epsilon_{t+h}$$

Because overlapping multi-period forward returns ($h > 1$) induce an $\text{MA}(h-1)$ error structure in OLS residuals, standard errors must be corrected using **Newey-West HAC** (Heteroskedasticity and Autocorrelation Consistent) covariance with a lag truncation parameter set to at least $h$.

### Python Implementation

```python
import numpy as np
import pandas as pd
import statsmodels.api as sm
from statsmodels.regression.linear_model import OLS

def run_multi_horizon_sentiment_regression(
    df: pd.DataFrame,
    price_col: str = "close",
    volume_col: str = "volume",
    sentiment_col: str = "sentiment_7d_sma",
    horizons: list[int] = [1, 3, 5, 10, 20]
) -> pd.DataFrame:
    """
    Runs multi-horizon predictive OLS regressions forecasting forward cumulative returns
    from current sentiment, controlling for past 1-day return and volume growth.
    
    Corrects standard errors using Newey-West HAC covariance.
    """
    df = df.copy().sort_index()

    # 1. Feature Engineering: Controls
    df["ret_lag1"] = df[price_col].pct_change(1)
    df["vol_growth"] = np.log(df[volume_col] + 1) - np.log(df[volume_col].shift(1) + 1)

    regression_results = []

    for h in horizons:
        # 2. Target Variable: Forward cumulative return over h trading days
        # R_{t -> t+h} = (Price_{t+h} - Price_t) / Price_t
        df[f"fwd_ret_{h}d"] = (df[price_col].shift(-h) - df[price_col]) / df[price_col]

        # 3. Model Matrix Construction
        feature_cols = [sentiment_col, "ret_lag1", "vol_growth"]
        model_data = df[[f"fwd_ret_{h}d"] + feature_cols].dropna()

        if len(model_data) < 30:
            continue

        y = model_data[f"fwd_ret_{h}d"]
        X = sm.add_constant(model_data[feature_cols])

        # 4. OLS Fit with Newey-West HAC Standard Errors
        # Lag bandwidth set to h + 1 to account for overlapping MA(h-1) errors
        hac_maxlags = max(1, h + 1)
        model = OLS(y, X).fit(cov_type="HAC", cov_kwds={"maxlags": hac_maxlags})

        # Extract metrics for sentiment beta
        sent_coef = model.params[sentiment_col]
        sent_tstat = model.tvalues[sentiment_col]
        sent_pval = model.pvalues[sentiment_col]

        regression_results.append({
            "horizon_days": f"t+{h}d",
            "sent_coef (beta)": sent_coef,
            "sent_tstat": sent_tstat,
            "sent_pval": sent_pval,
            "control_ret_coef": model.params["ret_lag1"],
            "control_ret_pval": model.pvalues["ret_lag1"],
            "control_vol_coef": model.params["vol_growth"],
            "control_vol_pval": model.pvalues["vol_growth"],
            "r_squared_adj": model.rsquared_adj,
            "observations": int(model.nobs)
        })

    results_df = pd.DataFrame(regression_results)
    return results_df

# Example setup with synthetic price/volume/sentiment data
if __name__ == "__main__":
    np.random.seed(42)
    dates = pd.date_range("2024-01-01", periods=250, freq="B")
    
    # Simulate data
    sim_close = 150 + np.cumsum(np.random.normal(0.05, 1.2, len(dates)))
    sim_volume = np.random.lognormal(16, 0.4, len(dates))
    sim_sentiment = np.random.uniform(-0.6, 0.8, len(dates))
    
    sample_df = pd.DataFrame({
        "close": sim_close,
        "volume": sim_volume,
        "sentiment_7d_sma": pd.Series(sim_sentiment).rolling(7, min_periods=1).mean().values
    }, index=dates)

    results = run_multi_horizon_sentiment_regression(
        sample_df,
        price_col="close",
        volume_col="volume",
        sentiment_col="sentiment_7d_sma",
        horizons=[1, 3, 5, 10, 20]
    )

    # Format table output for scanning
    print(results.to_string(index=False))

```

### Econometric Interpretations

* **Newey-West HAC Correction:** When evaluating overlapping forward windows (like 5-day or 20-day returns), consecutive observations share information ($t+1$ overlaps with $t, t+2, \dots$), violating the OLS zero-covariance error assumption. Standard OLS severely underestimates standard errors and inflates $t$-statistics; the HAC adjustment restores asymptotic consistency.
* **Economic Magnitude ($\beta_{1,h}$):** Because sentiment ranges from $[-1, +1]$, a $\beta_{1,5} = 0.02$ indicates that a 1.0 unit increase from neutral ($0.0$) to maximum bullish sentiment ($+1.0$) predicts an expected $+2.0\%$ forward return over the subsequent 5 trading days, holding prior return momentum and volume growth constant.
* **Mean Reversion vs. Momentum:**
* **Short Horizons ($t+1, t+3$):** If $\beta_{1,1} > 0$ and $p < 0.05$, price discovery is immediate.
* **Long Horizons ($t+10, t+20$):** If $\beta_{1,h}$ turns negative at extended horizons, sentiment is indicative of retail overreaction followed by subsequent price reversal.

An out-of-sample quintile backtest ranks a cross-sectional universe of assets by sentiment at each rebalancing date $t$, goes **long the top 20% (Q5)** and **short the bottom 20% (Q1)**, and measures realized returns strictly out-of-sample over the holding period $t \to t+1$.

```python
import numpy as np
import pandas as pd
import plotly.graph_objects as go

def run_quintile_long_short_backtest(
    prices: pd.DataFrame, 
    sentiment_scores: pd.DataFrame, 
    rebalance_freq: str = "W-FRI",
    transaction_cost_bps: float = 10.0,
    train_test_split_date: str = "2024-01-01"
) -> dict:
    """
    Constructs a cross-sectional dollar-neutral quintile portfolio (Long Q5, Short Q1).
    - Rebalances at frequency `rebalance_freq` using sentiment observed prior to close.
    - Applies a fixed one-way transaction cost (in bps) on rebalanced turnover.
    - Evaluates performance strictly Out-Of-Sample (OOS).
    """
    # 1. Compute Forward Multi-Period Holding Returns
    # Resample prices to rebalancing schedule
    reb_prices = prices.resample(rebalance_freq).last().dropna(how="all")
    # Forward period return: R_{t -> t+1} = (P_{t+1} - P_t) / P_t
    forward_returns = reb_prices.pct_change(1).shift(-1)

    # 2. Align Sentiment Signals (Observed at rebalance date t)
    reb_sentiment = sentiment_scores.resample(rebalance_freq).last().reindex(reb_prices.index)

    # Containers for quintile returns
    quintile_returns = {f"Q{i}": [] for i in range(1, 6)}
    long_short_returns = []
    dates = []

    # 3. Cross-Sectional Ranking Loop
    for t in reb_sentiment.index[:-1]:  # Exclude last timestamp since forward return is NaN
        sent_cross_section = reb_sentiment.loc[t].dropna()
        fwd_ret_cross_section = forward_returns.loc[t].dropna()

        # Intersect available assets with valid signal & return
        valid_assets = sent_cross_section.index.intersection(fwd_ret_cross_section.index)
        if len(valid_assets) < 10:  # Need sufficient universe breadth
            continue

        s = sent_cross_section.loc[valid_assets]
        r = fwd_ret_cross_section.loc[valid_assets]

        # Rank cross-sectionally into 5 bins (0: Q1/Worst, 4: Q5/Best)
        try:
            q_labels = pd.qcut(s, q=5, labels=[1, 2, 3, 4, 5], duplicates="drop")
        except ValueError:
            continue

        q_rets = {}
        for q in range(1, 6):
            q_tickers = valid_assets[q_labels == q]
            q_ret = r.loc[q_tickers].mean() if len(q_tickers) > 0 else 0.0
            quintile_returns[f"Q{q}"].append(q_ret)
            q_rets[f"Q{q}"] = q_ret

        # Long/Short Return = Long Q5 Return - Short Q1 Return - Roundtrip Costs
        # Cost factor: 2 legs * transaction_cost_bps / 10,000
        cost_penalty = 2.0 * (transaction_cost_bps / 10000.0)
        ls_net_return = q_rets["Q5"] - q_rets["Q1"] - cost_penalty

        long_short_returns.append(ls_net_return)
        dates.append(t)

    # 4. Assemble Portfolio Return DataFrames
    df_results = pd.DataFrame(quintile_returns, index=dates)
    df_results["Long_Short_Net"] = long_short_returns

    # 5. Out-of-Sample (OOS) Partitioning
    oos_df = df_results.loc[train_test_split_date:].copy()

    # Performance Metrics Calculation
    ann_factor = 52 if "W" in rebalance_freq else 252  # Weekly vs Daily factor
    mean_ret = oos_df["Long_Short_Net"].mean() * ann_factor
    volatility = oos_df["Long_Short_Net"].std() * np.sqrt(ann_factor)
    sharpe = mean_ret / (volatility + 1e-9)

    cum_ret = (1 + oos_df["Long_Short_Net"]).cumprod()
    running_max = cum_ret.cummax()
    drawdown = (cum_ret - running_max) / running_max
    max_dd = drawdown.min()

    metrics = {
        "Annualized Return": f"{mean_ret:.2%}",
        "Annualized Volatility": f"{volatility:.2%}",
        "Sharpe Ratio": f"{sharpe:.2f}",
        "Max Drawdown": f"{max_dd:.2%}",
        "OOS Periods": len(oos_df)
    }

    return {
        "full_results": df_results,
        "oos_results": oos_df,
        "metrics": metrics
    }

def plot_quintile_performance(oos_df: pd.DataFrame):
    fig = go.Figure()

    # Cumulative growth curves for each quintile + Long/Short
    for col in ["Q1", "Q2", "Q3", "Q4", "Q5"]:
        cum_q = (1 + oos_df[col]).cumprod()
        fig.add_trace(go.Scatter(x=oos_df.index, y=cum_q, name=col, opacity=0.6))

    cum_ls = (1 + oos_df["Long_Short_Net"]).cumprod()
    fig.add_trace(go.Scatter(
        x=oos_df.index, 
        y=cum_ls, 
        name="Long Q5 / Short Q1 (Net)", 
        line=dict(color="black", width=3)
    ))

    fig.update_layout(
        title="Out-of-Sample Quintile Performance & Long/Short Spread",
        xaxis_title="Rebalance Date",
        yaxis_title="Cumulative Return ($1.00 Base)",
        template="plotly_white",
        hovermode="x unified"
    )
    fig.show()

# Synthetic Universe Demo
if __name__ == "__main__":
    np.random.seed(42)
    dates = pd.date_range("2023-01-01", "2026-08-01", freq="B")
    tickers = [f"STOCK_{i:02d}" for i in range(50)]

    # Generate synthetic prices and sentiment panels
    sim_returns = pd.DataFrame(np.random.normal(0.0003, 0.02, size=(len(dates), len(tickers))), index=dates, columns=tickers)
    sim_prices = (1 + sim_returns).cumprod() * 100

    # Create sentiment with slight predictive edge
    sim_sentiment = sim_returns.shift(-5) * 5 + pd.DataFrame(np.random.normal(0, 1, size=(len(dates), len(tickers))), index=dates, columns=tickers)

    backtest = run_quintile_long_short_backtest(
        prices=sim_prices,
        sentiment_scores=sim_sentiment,
        rebalance_freq="W-FRI",
        transaction_cost_bps=10.0,
        train_test_split_date="2024-06-01"
    )

    print("--- Out-of-Sample Performance Summary ---")
    for k, v in backtest["metrics"].items():
        print(f"{k}: {v}")

    plot_quintile_performance(backtest["oos_results"])

```

### Quant Quality Checks for Cross-Sectional Factors

* **Monotonicity Requirement:** In a viable sentiment factor, cumulative returns across quintiles should scale strictly monotonically ($Q_5 > Q_4 > Q_3 > Q_2 > Q_1$). If $Q_2$ outperforms $Q_4$, the signal is driven by non-linear tails rather than a systematic premium.
* **Turnover & Cost Drag:** Sentiment changes rapidly compared to fundamental metrics. Tracking portfolio turnover between rebalance timestamps ensures transaction costs and short-borrow fees (hard-to-borrow stock drag in Q1) do not consume the long/short alpha.
* **Survivorship & Point-in-Time Alignment:** Ensure the asset universe $U_t$ reflects the historical index composition or liquidity filter at date $t$, rather than applying current survivors retroactively.

Sector neutralization removes macroeconomic and industry-wide sentiment bias (e.g., Tech receiving systematically higher sentiment than Utilities). Standardizing sentiment within each industry group ensures that your top quintile ($Q_5$) and bottom quintile ($Q_1$) select the strongest and weakest names **relative to their peers**, creating a balanced, sector-neutral portfolio.

For cross-sectional sentiment $S_{i,s,t}$ of asset $i$ in sector $s$ at timestamp $t$, the sector-neutral z-score is calculated as:

$$z_{i,s,t} = \frac{S_{i,s,t} - \mu_{s,t}}{\sigma_{s,t} + \epsilon}$$

where $\mu_{s,t}$ and $\sigma_{s,t}$ are the cross-sectional mean and standard deviation of sentiment across all assets in sector $s$ at date $t$.

### Python Implementation

```python
import numpy as np
import pandas as pd

def compute_sector_neutral_zscores(
    sentiment_df: pd.DataFrame,
    sector_map: pd.Series | dict,
    min_assets_per_sector: int = 3,
    winsorize_std: float = 3.0
) -> pd.DataFrame:
    """
    Transforms cross-sectional sentiment scores into sector-neutral z-scores per timestamp.
    
    Parameters:
    - sentiment_df: Wide DataFrame (index=dates, columns=tickers) of raw sentiment.
    - sector_map: Series or dict mapping ticker -> Sector/Industry name.
    - min_assets_per_sector: Minimum assets required in a sector to compute industry stats.
                             Falls back to universe-wide z-score if below threshold.
    - winsorize_std: Clips extreme outlier z-scores to [-winsorize_std, +winsorize_std].
    
    Returns:
    - DataFrame of standardized, sector-neutral sentiment signals.
    """
    # Convert sector map to pd.Series for alignment
    if isinstance(sector_map, dict):
        sector_series = pd.Series(sector_map)
    else:
        sector_series = sector_map.copy()

    neutralized_records = []

    # Iterate through each cross-section timestamp
    for date, row in sentiment_df.iterrows():
        valid_row = row.dropna()
        if len(valid_row) == 0:
            neutralized_records.append(pd.Series(index=sentiment_df.columns, dtype=float, name=date))
            continue

        # Create cross-sectional frame with Ticker, Sentiment, and Sector
        cs_df = pd.DataFrame({
            "ticker": valid_row.index,
            "sentiment": valid_row.values,
            "sector": sector_series.reindex(valid_row.index).fillna("Unknown")
        })

        # Step 1: Calculate Sector-Specific Mean and Std
        sector_stats = cs_df.groupby("sector")["sentiment"].agg(["mean", "std", "count"])

        # Universe fallback stats for tiny sectors
        univ_mean = cs_df["sentiment"].mean()
        univ_std = cs_df["sentiment"].std() if cs_df["sentiment"].std() > 1e-8 else 1.0

        def standardize(group):
            sec_name = group["sector"].iloc[0]
            sec_count = len(group)
            
            # If sector is too small or standard deviation is zero, use universe stats
            sec_std = group["sentiment"].std()
            if sec_count < min_assets_per_sector or pd.isna(sec_std) or sec_std < 1e-8:
                mean = univ_mean
                std = univ_std
            else:
                mean = group["sentiment"].mean()
                std = sec_std

            # Compute z-score
            group["zscore"] = (group["sentiment"] - mean) / std
            return group

        # Apply group-wise standardization
        standardized_cs = cs_df.groupby("sector", group_keys=False).apply(standardize)

        # Step 2: Winsorize extreme outlier z-scores (e.g., +/- 3.0 standard deviations)
        standardized_cs["zscore"] = standardized_cs["zscore"].clip(-winsorize_std, winsorize_std)

        # Step 3: Map back to date row
        z_series = standardized_cs.set_index("ticker")["zscore"].reindex(sentiment_df.columns)
        z_series.name = date
        neutralized_records.append(z_series)

    return pd.DataFrame(neutralized_records)

# Demo and Verification
if __name__ == "__main__":
    np.random.seed(42)
    dates = pd.date_range("2026-08-01", "2026-08-05", freq="B")
    
    # 10 tickers across 3 sectors
    tickers = ["AAPL", "MSFT", "NVDA", "JPM", "BAC", "GS", "XOM", "CVX", "COP", "SLB"]
    sector_lookup = {
        "AAPL": "Tech", "MSFT": "Tech", "NVDA": "Tech",
        "JPM": "Financials", "BAC": "Financials", "GS": "Financials",
        "XOM": "Energy", "CVX": "Energy", "COP": "Energy", "SLB": "Energy"
    }

    # Simulate raw sentiment: Tech biased high (+0.8 avg), Energy biased low (-0.4 avg)
    tech_sent = np.random.normal(0.8, 0.2, (len(dates), 3))
    fin_sent = np.random.normal(0.1, 0.15, (len(dates), 3))
    eng_sent = np.random.normal(-0.4, 0.2, (len(dates), 4))
    
    raw_sentiment = pd.DataFrame(
        np.hstack([tech_sent, fin_sent, eng_sent]), 
        index=dates, 
        columns=tickers
    )

    print("=== Raw Sentiment (Biased Across Sectors) ===")
    print(raw_sentiment.round(3))

    neutral_z = compute_sector_neutral_zscores(
        sentiment_df=raw_sentiment,
        sector_map=sector_lookup,
        min_assets_per_sector=3,
        winsorize_std=3.0
    )

    print("\n=== Sector-Neutral Z-Scores (Zero-Centered Per Sector) ===")
    print(neutral_z.round(3))

```

### Why Sector Neutralization Improves Factor Backtests

* **Eliminates Unintended Sector Bets:** Without neutralization, a long $Q_5$ / short $Q_1$ portfolio during a bull cycle in tech will simply load 100% long on Tech and 100% short on legacy industries, transforming a stock-selection strategy into a crude sector rotation bet.
* **Reduces Factor Collinearity:** It decorrelates the sentiment factor from macro risk factors (e.g., Fama-French industry factors, commodity cycle shocks), isolating the idiosyncratic alpha of individual companies.
* **Even Distribution Across Quintiles:** Because each sector's z-score distribution is centered at $\mu = 0$, every sector contributes proportionate long and short candidates into $Q_5$ and $Q_1$.

Residualizing sentiment against sector indicators and log market cap strips out both industry-wide biases and large-cap media coverage tilt.

At each cross-section $t$, we estimate the cross-sectional linear model across universe assets $i=1, \dots, N_t$:

$$S_{i,t} = \alpha_t + \beta_{\text{size},t} \ln(\text{MCap}_{i,t}) + \sum_{k=1}^{K-1} \gamma_{k,t} D_{i,k} + \epsilon_{i,t}$$

* $D_{i,k}$: Dummy indicator ($1$ if asset $i$ belongs to Sector $k$, $0$ otherwise; one sector omitted to prevent collinearity with the constant).
* $\ln(\text{MCap}_{i,t})$: Log market capitalization (size factor).
* $\epsilon_{i,t}$: **Residualized sentiment factor** (orthogonal to both sector exposure and size).

### Python Implementation

```python
import numpy as np
import pandas as pd
import statsmodels.api as sm
from statsmodels.regression.linear_model import OLS

def residualize_sentiment_cross_section(
    sentiment_df: pd.DataFrame,
    mcap_df: pd.DataFrame,
    sector_map: pd.Series | dict,
    min_assets: int = 15,
    winsorize_std: float = 3.0
) -> pd.DataFrame:
    """
    Residualizes sentiment scores cross-sectionally against log(market_cap) 
    and sector dummy variables for each timestamp t.
    
    Parameters:
    - sentiment_df: Wide DataFrame (index=dates, columns=tickers) of raw sentiment.
    - mcap_df: Wide DataFrame (index=dates, columns=tickers) of market caps.
    - sector_map: Series or dict mapping ticker -> Sector name.
    - min_assets: Minimum cross-sectional observations required to run regression.
    - winsorize_std: Truncation threshold for the final standardized residuals.
    
    Returns:
    - Wide DataFrame of standardized orthogonal sentiment residuals.
    """
    if isinstance(sector_map, dict):
        sector_series = pd.Series(sector_map)
    else:
        sector_series = sector_map.copy()

    residual_rows = []

    for date in sentiment_df.index:
        # Align sentiment and market cap for date t
        s_t = sentiment_df.loc[date].dropna()
        m_t = mcap_df.loc[date].dropna() if date in mcap_df.index else pd.Series(dtype=float)

        common_tickers = s_t.index.intersection(m_t.index).intersection(sector_series.dropna().index)

        if len(common_tickers) < min_assets:
            residual_rows.append(pd.Series(index=sentiment_df.columns, dtype=float, name=date))
            continue

        # 1. Build Cross-Sectional Frame
        cs = pd.DataFrame({
            "sentiment": s_t.loc[common_tickers].values,
            "log_mcap": np.log(m_t.loc[common_tickers].astype(float).values),
            "sector": sector_series.loc[common_tickers].values
        }, index=common_tickers)

        # 2. Construct Design Matrix: Log MCap + One-Hot Sector Dummies (drop_first=True to avoid dummy trap)
        sector_dummies = pd.get_dummies(cs["sector"], drop_first=True, dtype=float)
        X = pd.concat([cs[["log_mcap"]], sector_dummies], axis=1)
        X = sm.add_constant(X)
        y = cs["sentiment"]

        # 3. Fit Cross-Sectional OLS & Extract Residuals (epsilon)
        try:
            model = OLS(y, X).fit()
            residuals = model.resid

            # 4. Standardize (z-score) and winsorize residuals across the cross-section
            res_std = residuals.std()
            if res_std > 1e-8:
                norm_residuals = (residuals - residuals.mean()) / res_std
                norm_residuals = norm_residuals.clip(-winsorize_std, winsorize_std)
            else:
                norm_residuals = residuals * 0.0

            out_series = norm_residuals.reindex(sentiment_df.columns)
            out_series.name = date
            residual_rows.append(out_series)

        except np.linalg.LinAlgError:
            # Fallback if matrix is singular
            residual_rows.append(pd.Series(index=sentiment_df.columns, dtype=float, name=date))

    return pd.DataFrame(residual_rows)

# Simulation & Verification
if __name__ == "__main__":
    np.random.seed(42)
    dates = pd.date_range("2026-08-01", periods=5, freq="B")
    
    tickers = [f"TICK_{i:02d}" for i in range(20)]
    sectors = ["Tech"] * 7 + ["Financials"] * 7 + ["Energy"] * 6
    sec_lookup = dict(zip(tickers, sectors))

    # Simulate market caps (Megacap Tech vs Midcap Energy)
    base_mcap = np.array([2e12]*7 + [4e11]*7 + [8e10]*6)
    mcap_panel = pd.DataFrame(
        np.tile(base_mcap, (len(dates), 1)) * np.random.uniform(0.98, 1.02, (len(dates), 20)),
        index=dates,
        columns=tickers
    )

    # Simulate raw sentiment: Strong positive correlation with size and sector
    log_m = np.log(mcap_panel.values)
    raw_sent = 0.3 * (log_m - log_m.mean()) + np.random.normal(0, 0.4, (len(dates), 20))
    sentiment_panel = pd.DataFrame(raw_sent, index=dates, columns=tickers)

    # Run Residualization
    pure_alpha = residualize_sentiment_cross_section(
        sentiment_df=sentiment_panel,
        mcap_df=mcap_panel,
        sector_map=sec_lookup,
        min_assets=15
    )

    # Check correlation with log market cap before and after
    d0 = dates[0]
    log_mcap_d0 = np.log(mcap_panel.loc[d0])
    corr_before = np.corrcoef(sentiment_panel.loc[d0], log_mcap_d0)[0, 1]
    corr_after = np.corrcoef(pure_alpha.loc[d0], log_mcap_d0)[0, 1]

    print(f"Correlation with Log Market Cap (Raw Sentiment):       {corr_before:.4f}")
    print(f"Correlation with Log Market Cap (Residualized Signal): {corr_after:.4f}")
    print("\nSample Residualized Signals (Top 5 Tickers):")
    print(pure_alpha.iloc[:, :5].round(3))

```

### Key Mathematical & Practical Takeaways

* **Strict Orthogonality:** The sample correlation between `pure_alpha` and `log_mcap` (as well as sector dummy projections) drops to **`0.0000`** by construction of OLS projection geometry ($X^T e = 0$).
* **Dummy Variable Trap:** Setting `drop_first=True` in `pd.get_dummies` omits one baseline category, ensuring $X$ maintains full column rank alongside the intercept `const`.
* **Pure Idiosyncratic Signal:** Large-cap stocks receive substantially more news mentions, producing structurally tighter sentiment variance than illiquid mid-caps. Residualizing eliminates the "Mega-Cap Beta" from the signal before building factor portfolios.

The **Information Coefficient (IC)** measures the cross-sectional correlation between a factor signal at date $t$ and forward returns over holding period $t \to t+h$:

* **Pearson Normal IC ($\rho_{\text{Pearson}}$):** Linear correlation evaluating raw magnitude predictive power.
* **Rank IC ($\rho_{\text{Spearman}}$):** Rank correlation evaluating monotonic ordering (robust to outliers and heavy-tailed distributions).
* **Information Ratio ($\text{IR}_{\text{IC}}$):** $\frac{\text{Mean}(\text{IC})}{\text{Std}(\text{IC})} \times \sqrt{N_{\text{periods}}}$, assessing signal consistency.

### Python Implementation

```python
import numpy as np
import pandas as pd
from scipy import stats
import plotly.graph_objects as go
from plotly.subplots import make_subplots

def compute_rolling_information_coefficient(
    signal_df: pd.DataFrame,
    price_df: pd.DataFrame,
    holding_period: int = 5,
    min_assets: int = 15,
    rolling_window: int = 12
) -> dict:
    """
    Computes cross-sectional Pearson IC, Rank IC (Spearman), and rolling IC stats.
    
    Parameters:
    - signal_df: Wide DataFrame (dates x tickers) of standardized/residualized signals.
    - price_df: Wide DataFrame (dates x tickers) of asset prices.
    - holding_period: Forward return horizon in trading days (h).
    - min_assets: Minimum cross-sectional assets required per timestamp.
    - rolling_window: Window size for rolling mean IC and IC-IR.
    """
    # 1. Compute Forward h-period Returns: R_{t -> t+h} = (Price_{t+h} - Price_t) / Price_t
    forward_returns = (price_df.shift(-holding_period) - price_df) / price_df

    ic_records = []

    # 2. Cross-Sectional Correlation Loop
    for date in signal_df.index:
        if date not in forward_returns.index:
            continue

        s_t = signal_df.loc[date].dropna()
        r_t = forward_returns.loc[date].dropna()

        common_assets = s_t.index.intersection(r_t.index)
        if len(common_assets) < min_assets:
            continue

        s_aligned = s_t.loc[common_assets]
        r_aligned = r_t.loc[common_assets]

        # Cross-sectional Pearson and Spearman Rank IC
        pearson_ic, p_val = stats.pearsonr(s_aligned, r_aligned)
        rank_ic, rank_p_val = stats.spearmanr(s_aligned, r_aligned)

        ic_records.append({
            "date": date,
            "pearson_ic": pearson_ic,
            "rank_ic": rank_ic,
            "p_value": rank_p_val,
            "asset_count": len(common_assets)
        })

    ic_df = pd.DataFrame(ic_records).set_index("date")

    # 3. Time-Series Rolling Statistics
    ic_df["rolling_rank_ic"] = ic_df["rank_ic"].rolling(rolling_window, min_periods=max(3, rolling_window // 2)).mean()
    ic_df["cum_rank_ic"] = ic_df["rank_ic"].cumsum()

    # Annualization factor based on frequency (approx 52 for weekly rebalancing, 252 for daily)
    ann_factor = np.sqrt(252 / holding_period)
    
    # 4. Summary Performance Metrics
    mean_rank_ic = ic_df["rank_ic"].mean()
    std_rank_ic = ic_df["rank_ic"].std()
    ic_ir = (mean_rank_ic / (std_rank_ic + 1e-9)) * ann_factor
    pct_positive = (ic_df["rank_ic"] > 0).mean()

    # t-statistic for H0: Mean(IC) == 0
    t_stat, t_pval = stats.ttest_1samp(ic_df["rank_ic"].dropna(), popmean=0.0)

    summary_metrics = {
        "Mean Rank IC": f"{mean_rank_ic:.4f}",
        "Mean Pearson IC": f"{ic_df['pearson_ic'].mean():.4f}",
        "IC Standard Deviation": f"{std_rank_ic:.4f}",
        "Annualized IC Information Ratio (IR)": f"{ic_ir:.2f}",
        "Positive IC Ratio": f"{pct_positive:.1%}",
        "IC t-statistic": f"{t_stat:.2f} (p={t_pval:.4f})",
        "Sample Periods": len(ic_df)
    }

    return {
        "ic_series": ic_df,
        "metrics": summary_metrics
    }

def plot_ic_diagnostics(ic_df: pd.DataFrame, ticker_or_strategy: str = "Residualized Sentiment"):
    fig = make_subplots(
        rows=2, cols=1,
        shared_xaxes=True,
        vertical_spacing=0.08,
        subplot_titles=("Cross-Sectional Rank IC & Rolling Mean", "Cumulative Rank IC")
    )

    # Subplot 1: Bar chart for Period Rank IC + Line for Rolling Mean
    bar_colors = ["#2ca02c" if x > 0 else "#d62728" for x in ic_df["rank_ic"]]
    fig.add_trace(
        go.Bar(x=ic_df.index, y=ic_df["rank_ic"], marker_color=bar_colors, opacity=0.5, name="Rank IC"),
        row=1, col=1
    )
    fig.add_trace(
        go.Scatter(x=ic_df.index, y=ic_df["rolling_rank_ic"], line=dict(color="#1f77b4", width=2.5), name="Rolling Mean IC"),
        row=1, col=1
    )
    fig.add_hline(y=0.0, line_width=1, line_dash="solid", line_color="black", row=1, col=1)

    # Subplot 2: Cumulative Rank IC
    fig.add_trace(
        go.Scatter(x=ic_df.index, y=ic_df["cum_rank_ic"], line=dict(color="#9467bd", width=2), name="Cumulative Rank IC"),
        row=2, col=1
    )

    fig.update_layout(
        title=f"{ticker_or_strategy} — Factor IC Diagnostics",
        template="plotly_white",
        hovermode="x unified",
        height=650
    )
    fig.show()

# Verification with synthetic multi-asset panel
if __name__ == "__main__":
    np.random.seed(42)
    dates = pd.date_range("2025-01-01", "2026-08-01", freq="W-FRI")
    tickers = [f"EQ_{i:02d}" for i in range(30)]

    # Generate synthetic price returns and sentiment with an intentional positive predictive tilt
    sim_ret = pd.DataFrame(np.random.normal(0.001, 0.03, size=(len(dates), len(tickers))), index=dates, columns=tickers)
    sim_prices = (1 + sim_ret).cumprod() * 100

    # True signal with noise
    signal_tilt = sim_ret.shift(-1) * 3.0 + np.random.normal(0, 1.0, size=(len(dates), len(tickers)))
    sim_signals = pd.DataFrame(signal_tilt, index=dates, columns=tickers)

    results = compute_rolling_information_coefficient(
        signal_df=sim_signals,
        price_df=sim_prices,
        holding_period=1,
        min_assets=20,
        rolling_window=8
    )

    print("=== Factor IC Performance Summary ===")
    for k, v in results["metrics"].items():
        print(f"{k}: {v}")

    plot_ic_diagnostics(results["ic_series"])

```

### Institutional Benchmarks for Sentiment Factors

* **Mean Rank IC:** A Rank IC between **`0.02` and `0.05**` is typical for alternative sentiment signals; $\text{IC} > 0.05$ indicates a strong factor.
* **Information Ratio ($\text{IR}_{\text{IC}}$):** A signal $\text{IR} > 1.0$ is generally considered production-grade and deployable in multi-factor alpha models.
* **Positive IC Ratio ($\% \text{ Positive}$):** Should ideally exceed **`55%–60%`** across all rebalance intervals to ensure alpha generation is not concentrated in a handful of isolated market events.

An **IC Term Structure** (or alpha decay curve) evaluates the cross-sectional predictive power of a factor across increasing forward horizons ($h = 1, 2, 3, \dots, H$ trading days).

For sentiment and news signals, alpha decays rapidly: measuring the half-life of Rank IC helps determine the optimal **rebalancing frequency** and **portfolio holding period**.

### Python Implementation

This script computes cross-sectional Pearson and Spearman Rank IC across holding periods $h \in [1, 30]$ trading days, calculates $t$-statistics and IC-IR for each horizon, and plots the decay profile with a fitted exponential half-life curve.

```python
import numpy as np
import pandas as pd
from scipy import stats, optimize
import plotly.graph_objects as go
from plotly.subplots import make_subplots

def compute_ic_term_structure(
    signal_df: pd.DataFrame,
    price_df: pd.DataFrame,
    max_horizon: int = 30,
    min_assets: int = 15
) -> pd.DataFrame:
    """
    Computes cross-sectional Rank IC and Pearson IC term structure from 1 to max_horizon days.
    
    Parameters:
    - signal_df: Wide DataFrame (dates x tickers) of cross-sectional factor signals.
    - price_df: Wide DataFrame (dates x tickers) of daily close prices.
    - max_horizon: Max forward horizon in trading days (default 30).
    - min_assets: Minimum cross-sectional assets required per date.
    
    Returns:
    - DataFrame indexed by forward horizon h containing Mean IC, IR, t-stat, and p-value.
    """
    horizons = list(range(1, max_horizon + 1))
    term_structure_records = []

    for h in horizons:
        # Forward cumulative return over h days: R_{t -> t+h} = (Price_{t+h} - Price_t) / Price_t
        fwd_return_h = (price_df.shift(-h) - price_df) / price_df

        rank_ics = []
        pearson_ics = []

        for date in signal_df.index:
            if date not in fwd_return_h.index:
                continue

            s_t = signal_df.loc[date].dropna()
            r_t = fwd_return_h.loc[date].dropna()

            common_tickers = s_t.index.intersection(r_t.index)
            if len(common_tickers) < min_assets:
                continue

            s_aligned = s_t.loc[common_tickers]
            r_aligned = r_t.loc[common_tickers]

            # Cross-sectional correlation
            p_ic, _ = stats.pearsonr(s_aligned, r_aligned)
            r_ic, _ = stats.spearmanr(s_aligned, r_aligned)

            rank_ics.append(r_ic)
            pearson_ics.append(p_ic)

        if not rank_ics:
            continue

        rank_ics = np.array(rank_ics)
        pearson_ics = np.array(pearson_ics)

        mean_rank_ic = np.mean(rank_ics)
        std_rank_ic = np.std(rank_ics, ddof=1)
        
        # Newey-West adjusted or standard 1-sample t-test for H0: mean IC == 0
        t_stat, p_val = stats.ttest_1samp(rank_ics, popmean=0.0)
        
        # Annualized IC-IR assuming daily evaluation steps
        ic_ir = (mean_rank_ic / (std_rank_ic + 1e-9)) * np.sqrt(252 / h)

        term_structure_records.append({
            "horizon_days": h,
            "mean_rank_ic": mean_rank_ic,
            "mean_pearson_ic": np.mean(pearson_ics),
            "std_rank_ic": std_rank_ic,
            "ic_ir": ic_ir,
            "t_stat": t_stat,
            "p_value": p_val,
            "pct_positive": np.mean(rank_ics > 0)
        })

    return pd.DataFrame(term_structure_records).set_index("horizon_days")

def plot_ic_term_structure(term_df: pd.DataFrame, factor_name: str = "Residualized Sentiment"):
    horizons = term_df.index.values
    rank_ic = term_df["mean_rank_ic"].values

    # Fit exponential decay: IC(h) = IC_0 * exp(-lambda * h)
    def exp_decay(h, ic0, lmbda):
        return ic0 * np.exp(-lmbda * h)

    try:
        popt, _ = optimize.curve_fit(exp_decay, horizons, rank_ic, p0=[rank_ic[0], 0.05], maxfev=2000)
        fitted_ic = exp_decay(horizons, *popt)
        half_life = np.log(2) / popt[1] if popt[1] > 0 else np.nan
        half_life_text = f"Half-Life: {half_life:.1f} days" if not np.isnan(half_life) else "Decay: Non-exponential"
    except Exception:
        fitted_ic = None
        half_life_text = "Fitted curve unavailable"

    # Create subplots: Top = Mean IC & Decay Curve, Bottom = IC-IR & Statistical Significance
    fig = make_subplots(
        rows=2, cols=1,
        shared_xaxes=True,
        vertical_spacing=0.1,
        subplot_titles=(f"Mean Rank IC Term Structure ({half_life_text})", "Annualized IC Information Ratio (IR)")
    )

    # 1. Main IC Curve
    fig.add_trace(
        go.Scatter(
            x=horizons, 
            y=rank_ic, 
            mode="lines+markers", 
            name="Mean Rank IC", 
            line=dict(color="#1f77b4", width=2.5),
            marker=dict(size=6)
        ),
        row=1, col=1
    )

    if fitted_ic is not None:
        fig.add_trace(
            go.Scatter(
                x=horizons, 
                y=fitted_ic, 
                mode="lines", 
                name="Exponential Fit", 
                line=dict(color="#d62728", dash="dash", width=1.8)
            ),
            row=1, col=1
        )

    fig.add_hline(y=0.0, line_dash="solid", line_color="black", row=1, col=1)

    # 2. Information Ratio Bar Chart (Color by p-value < 0.05)
    colors = ["#2ca02c" if p < 0.05 else "#aec7e8" for p in term_df["p_value"]]
    fig.add_trace(
        go.Bar(
            x=horizons, 
            y=term_df["ic_ir"], 
            marker_color=colors, 
            name="IC-IR (Green: p < 0.05)"
        ),
        row=2, col=1
    )
    fig.add_hline(y=1.0, line_dash="dot", line_color="gray", annotation_text="IR=1.0 Threshold", row=2, col=1)

    fig.update_layout(
        title=f"{factor_name} — Alpha Decay & Term Structure Profile (1 to {max(horizons)} Days)",
        xaxis2_title="Holding Horizon (Trading Days)",
        yaxis_title="Rank IC",
        yaxis2_title="Annualized IC-IR",
        template="plotly_white",
        hovermode="x unified",
        height=700
    )

    fig.show()

# Synthetic Verification Panel
if __name__ == "__main__":
    np.random.seed(42)
    dates = pd.date_range("2024-01-01", "2026-08-01", freq="B")
    tickers = [f"ASSET_{i:02d}" for i in range(40)]

    # Generate synthetic price panel with random walk
    daily_returns = pd.DataFrame(
        np.random.normal(0.0004, 0.018, size=(len(dates), len(tickers))), 
        index=dates, 
        columns=tickers
    )
    price_panel = (1 + daily_returns).cumprod() * 100

    # Simulate fast-decaying sentiment signal (strongest at t+1 to t+3, fades by t+15)
    fwd_ret_3d = (price_panel.shift(-3) - price_panel) / price_panel
    pure_noise = pd.DataFrame(np.random.normal(0, 1.0, size=(len(dates), len(tickers))), index=dates, columns=tickers)
    sim_signal = fwd_ret_3d * 6.0 + pure_noise

    # Compute Term Structure
    term_structure = compute_ic_term_structure(
        signal_df=sim_signal,
        price_df=price_panel,
        max_horizon=30,
        min_assets=25
    )

    print("=== IC Term Structure Summary (First 10 Horizons) ===")
    print(term_structure[["mean_rank_ic", "ic_ir", "t_stat", "p_value"]].head(10).round(4))

    plot_ic_term_structure(term_structure, factor_name="Residualized Sentiment Factor")

```

### Analyzing the Alpha Decay Profile

| Decay Pattern | Curve Shape | Strategy Takeaway |
| --- | --- | --- |
| **Fast Alpha (Half-Life 1–3 Days)** | Sharp drop between $t+1$ and $t+5$. Returns approach zero or noise beyond day 5. | High turnover strategy required. Weekly/daily rebalance; execution algorithms must minimize market impact. |
| **Medium Alpha (Half-Life 5–15 Days)** | Peak IC achieved around $t+3$ to $t+7$, followed by gradual dissipation. | Best suited for bi-weekly or monthly rebalancing. Allows lower trading cost overhead. |
| **Inverted Decay / Overreaction Peak** | Initial positive IC followed by negative IC at $t+20$ to $t+30$. | Sentiment causes temporary price dislocation followed by long-term mean reversion. Pair with a reversal factor. |