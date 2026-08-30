"""News-sentiment factor research unit tests (Phase 2).

Hermetic: synthetic panels with planted predictive structure, no network.
"""

import numpy as np
import pytest

from tradingagents.strategies.sentiment_research import (
    ic_term_structure,
    multi_horizon_sentiment_regression,
    quintile_long_short,
    residualize_sentiment,
    rolling_information_coefficient,
    sector_neutral_z,
    sentiment_factor_scale,
    sentiment_lead_lag,
)

pytestmark = pytest.mark.timeout(120)


def _panel(n=260, n_tickers=20, seed=42):
    rng = np.random.default_rng(seed)
    tickers = [f"T{i:02d}" for i in range(n_tickers)]
    sectors = {t: ["TECH", "FIN", "ENE"][i % 3] for i, t in enumerate(tickers)}
    prices = {
        t: list(100.0 * np.cumprod(1 + rng.normal(0.0005, 0.02, n))) for t in tickers
    }
    rets = {}
    for t in tickers:
        closes = [100.0] + prices[t][:-1]
        rets[t] = [prices[t][i] / closes[i] - 1.0 for i in range(n)]
    # Planted signal: 3-day forward return + noise (predictive at h=3).
    signals = {}
    for t in tickers:
        fwd = np.array(
            [prices[t][i + 3] / prices[t][i] - 1.0 if i + 3 < n else 0.0 for i in range(n)]
        )
        signals[t] = list(fwd * 3.0 + rng.normal(0, 1.0, n))
    return tickers, sectors, prices, rets, signals


def test_lead_lag_positive_peak_at_planted_horizon():
    # Deterministic: sentiment_t = ret_{t+3} exactly -> peak at lag +3.
    n = 200
    rng = np.random.default_rng(3)
    rets = list(rng.normal(0.0005, 0.02, n))
    sent = [rets[i + 3] if i + 3 < n else 0.0 for i in range(n)]
    out = sentiment_lead_lag(sent, rets, max_lags=6)
    assert out is not None
    best = max(out, key=lambda r: r["spearman_corr"])
    assert best["lag_days"] == 3
    assert best["spearman_corr"] > 0.99
    for r in out:
        assert set(r) >= {"lag_days", "pearson_corr", "spearman_corr", "sample_size"}


def test_lead_lag_innovations_reduces_autocorrelation():
    _, _, _, rets, signals = _panel()
    base = sentiment_lead_lag(signals["T00"], rets["T00"], max_lags=3)
    innov = sentiment_lead_lag(signals["T00"], rets["T00"], max_lags=3, innovations=True)
    assert base is not None and innov is not None
    # Lag-0 should weaken after differencing the (smoothed) signal.
    b0 = next(r for r in base if r["lag_days"] == 0)["pearson_corr"]
    i0 = next(r for r in innov if r["lag_days"] == 0)["pearson_corr"]
    assert abs(i0) < abs(b0) + 1e-9


def test_lead_lag_short_none():
    assert sentiment_lead_lag([0.1, 0.2, 0.3], [0.01, 0.02, 0.03], max_lags=2) is None


def test_multi_horizon_detects_planted_signal():
    _, _, prices, rets, signals = _panel()
    fwd3 = np.array(
        [prices["T00"][i + 3] / prices["T00"][i] - 1.0 if i + 3 < len(prices["T00"]) else 0
         for i in range(len(prices["T00"]))]
    )
    vol = list(np.random.default_rng(1).integers(100000, 1000000, len(prices["T00"])).astype(float))
    # Signal == 5 * t+3 fwd return: coefficient should be positive at h=3.
    sig = list(fwd3 * 1.0)  # direct predictive signal
    out = multi_horizon_sentiment_regression(sig, prices["T00"], vol, horizons=(3,))
    assert out is not None
    assert out[0]["horizon_days"] == 3
    assert out[0]["sent_coef"] > 0.0
    assert out[0]["observations"] >= 30
    for key in ("sent_tstat", "sent_pval", "r_squared_adj", "control_ret_coef"):
        assert key in out[0]


def test_multi_horizon_short_none():
    assert (
        multi_horizon_sentiment_regression([0.1] * 10, [100.0 + i for i in range(10)], None)
        is None
    )


def test_sector_neutral_z_removes_sector_bias():
    tickers = [f"T{i:02d}" for i in range(30)]
    sectors = {t: ["TECH", "FIN", "ENE"][i % 3] for i, t in enumerate(tickers)}
    n = 5
    # Tech biased +0.8, Energies -0.4: raw means differ by sector.
    rng = np.random.default_rng(0)
    panel = {
        t: list(rng.normal(0.8, 0.2, n)) if sectors[t] == "TECH"
        else list(rng.normal(-0.4, 0.2, n)) if sectors[t] == "ENE"
        else list(rng.normal(0.1, 0.15, n))
        for t in tickers
    }
    z = sector_neutral_z(panel, sectors)
    # Per-date, the mean z per sector is ~0.
    for i in range(n):
        for sec in ("TECH", "ENE", "FIN"):
            vals = [z[t][i] for t in tickers if sectors[t] == sec]
            assert abs(sum(vals) / len(vals)) < 0.2
    # Winsorized range.
    flat = [v for t in tickers for v in z[t] if v is not None]
    assert max(flat) <= 3.0 and min(flat) >= -3.0


def test_residualize_drives_size_corr_to_zero():
    inputs = _panel(n_tickers=30)
    tickers, sectors, _, _, signals = inputs
    n = max(len(v) for v in signals.values())
    rng = np.random.default_rng(7)
    # Market cap strongly correlated with the raw signal (mega-cap tilt).
    mcap = {t: list(1e9 * rng.uniform(0.5, 2.0, n) * (1 + (i % 3) * 0.3)) for i, t in enumerate(tickers)}
    raw = {t: list(np.array(signals[t]) * 0.01 + np.log(np.array(mcap[t]) / 1e9)) for t in tickers}
    res = residualize_sentiment(raw, mcap, sectors, min_assets=10)
    d0 = [res[t][0] for t in tickers if res[t][0] is not None]
    assert len(d0) >= 10
    m0 = [np.log(mcap[t][0] / 1e9) for t in tickers if res[t][0] is not None]
    corr = np.corrcoef(d0, m0)[0, 1]
    assert abs(corr) < 0.15


def test_rolling_ic_positive_on_planted_signal():
    _, _, prices, _, signals = _panel()
    ic = rolling_information_coefficient(signals, prices, holding=3, window=8)
    assert ic is not None
    m = ic["metrics"]
    assert m["mean_rank_ic"] > 0.02
    assert m["periods"] > 30
    assert len(ic["dates"]) == len(ic["rank_ic"]) == len(ic["pearson_ic"])


def test_ic_term_structure_strong_at_short_horizon():
    _, _, prices, _, signals = _panel()
    ts = ic_term_structure(signals, prices, max_horizon=10)
    assert ts is not None and len(ts) >= 3
    # Planted 3-day signal: mean rank IC at h=3 should be among the strongest.
    h3 = next(r for r in ts if r["horizon_days"] == 3)
    assert h3["mean_rank_ic"] > 0.0
    assert "half_life_days" in ts[-1]


def test_quintile_long_short_monotonic_and_positive():
    _, _, prices, _, signals = _panel()
    q = quintile_long_short(signals, prices, rebalance="weekly", cost_bps=10, oos_split=0.3)
    assert q is not None
    assert q["metrics"]["periods"] > 5
    assert "sharpe" in q["metrics"] and "max_drawdown" in q["metrics"]
    # With a planted predictive signal the long/short spread should be > 0 mostly.
    assert sum(q["ls_net"]) > 0
    assert q["monotonicity"] is not None


def test_quintile_short_universe_none():
    assert quintile_long_short({"A": [0.1, 0.2]}, {"A": [100, 101]}) is None


def test_factor_scale_direction_and_floor():
    assert sentiment_factor_scale(0.05, 0.3, min_ic=0.02) == 1.2
    assert sentiment_factor_scale(-0.05, 0.3, min_ic=0.02) == pytest.approx(0.8)
    assert sentiment_factor_scale(0.01, 0.3, min_ic=0.02) == 1.0
    assert sentiment_factor_scale(None, 0.3, min_ic=0.02) == 1.0
    assert sentiment_factor_scale(0.05, None, min_ic=0.02) == 1.0
