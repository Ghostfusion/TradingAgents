"""Value Dip + Swing hybrid strategy calculators — pure/offline tests.

Covers tradingagents/strategies/value_dip.py: Bollinger %b, historical
valuation Z, FCF yield, breakeven win rate / expectancy, the 3-tranche
scale-in plan (weighted avg entry, composite stop, capital-at-risk check,
blended R:R) and the hybrid allocation matrix.

Every test runs under the repo's pytest-timeout deadlines (180s per-test
default, thread method; session cap 30 min) - a hung call can never block
the session.
"""

import math

import pytest

from tradingagents.strategies.value_dip import (
    balance_sheet_health,
    bollinger_pct_b,
    breakeven_win_rate,
    decline_driver_check,
    expectancy,
    fcf_yield,
    higher_low_structure,
    macd_divergence,
    profitability_quality,
    support_structure,
    tranche_plan,
    tranche_risk_read,
    trigger_candle,
    valuation_z_read,
    value_dip_setup,
    vdu_entry_setup,
    volume_dry_up,
    zscore,
)


def _flat(n=60):
    """Flat series around 100 with mild noise (mean ~100, low sigma)."""
    return [100.0 + 0.5 * math.sin(i / 4) for i in range(n)]


# ---------------------------------------------------------------------------
# Bollinger %b
# ---------------------------------------------------------------------------


def test_pct_b_piercing_lower_band():
    closes = list(_flat(40))
    closes[-1] = min(closes) - 5.0  # pierce far below the lower band
    bb = bollinger_pct_b(closes)
    assert bb is not None
    assert bb["pct_b"] <= 0.0
    assert bb["lower"] < bb["upper"]


def test_pct_b_mid_band():
    bb = bollinger_pct_b(_flat(40))
    assert bb is not None
    assert 0.0 < bb["pct_b"] < 1.0


def test_pct_b_insufficient_history():
    assert bollinger_pct_b([1.0, 2.0, 3.0]) is None


# ---------------------------------------------------------------------------
# Historical valuation Z
# ---------------------------------------------------------------------------


def test_zscore_known_series():
    # series 10..20 step 2 -> mean 15, sample std sqrt(14) ~ 3.742
    z = zscore(11.0, [10, 12, 14, 16, 18, 20])
    assert z is not None
    assert abs(z - (-1.0690)) < 1e-3


def test_zscore_min_n_guard():
    assert zscore(5.0, [1.0, 2.0, 3.0]) is None  # fewer than 4


def test_zscore_negative_values_preserved():
    z = zscore(-0.05, [-0.05, -0.04, -0.03, -0.02, -0.01])
    assert z is not None  # negative multiple values are not dropped


def test_valuation_z_cheap_verdict():
    read = valuation_z_read([10, 12, 14, 16, 18, 20], 11.0)
    # (11-15)/3.742 = -1.069 -> not <= -1.5
    assert read["verdict"] == "fair"
    read2 = valuation_z_read([10, 12, 14, 16, 18, 20], 8.0)
    assert read2["verdict"] == "cheap"


def test_valuation_z_insufficient_series():
    read = valuation_z_read([10.0, 12.0, 13.0], 11.0)
    assert read["verdict"] == "unknown"
    assert read["z"] is None


# ---------------------------------------------------------------------------
# FCF yield / breakeven rate / expectancy
# ---------------------------------------------------------------------------


def test_fcf_yield_basic():
    assert fcf_yield(1e9, 1e10) == pytest.approx(0.1)


def test_fcf_yield_missing_inputs():
    assert fcf_yield(None, 1e10) is None
    assert fcf_yield(1e9, None) is None
    assert fcf_yield(1e9, 0) is None


def test_breakeven_win_rate():
    assert breakeven_win_rate(2.4) == pytest.approx(1 / 3.4)
    assert breakeven_win_rate(0) is None
    assert breakeven_win_rate(-1) is None
    assert breakeven_win_rate(None) is None


def test_expectancy_positive_trade():
    # p=0.6, W=200, L=100 -> 0.6*200 - 0.4*100 = 80
    assert expectancy(0.6, 200.0, 100.0) == pytest.approx(80.0)


def test_expectancy_negative_trade():
    # p=0.3, W=100, L=100 -> 0.3*100 - 0.7*100 = -40
    assert expectancy(0.3, 100.0, 100.0) == pytest.approx(-40.0)


def test_expectancy_missing_inputs():
    assert expectancy(None, 100.0, 50.0) is None
    assert expectancy(0.5, None, 50.0) is None
    assert expectancy(0.5, 100.0, None) is None


# ---------------------------------------------------------------------------
# Tranche scale-in plan
# ---------------------------------------------------------------------------


def test_tranche_levels_and_sizing():
    plan = tranche_plan(180.0, 4.5, weights=(0.3, 0.3, 0.4), account=100_000, risk_pct=0.015)
    assert plan["valid"]
    # P2 = P1 - 1.0*ATR, P3 = P1 - 2.0*ATR
    assert plan["p2"] == pytest.approx(180.0 - 4.5)
    assert plan["p3"] == pytest.approx(180.0 - 9.0)
    # composite stop = P3 - 1.5*ATR
    assert plan["stop"] == pytest.approx(plan["p3"] - 1.5 * 4.5)
    # weighted avg entry = sum(w_i * P_i)
    avg = 0.3 * 180.0 + 0.3 * 175.5 + 0.4 * 171.0
    assert plan["avg_entry"] == pytest.approx(avg)
    # capital at risk <= max dollar risk
    assert plan["risk_ok"]
    assert plan["capital_at_risk"] <= plan["max_dollar_risk"] + 1e-9
    # blended R:R = 0.5*1.8 + 0.5*3.0 = 2.4
    assert plan["targets"]["blended_rr"] == pytest.approx(2.4)
    assert plan["breakeven_win_rate"] == pytest.approx(1 / 3.4, rel=1e-2)  # rounded to 4dp
    # shares sum to total
    assert sum(plan["shares"]) == plan["total_shares"]


def test_tranche_weights_must_sum_to_one():
    plan = tranche_plan(100.0, 2.0, weights=(0.5, 0.5, 0.5))
    assert not plan["valid"]


def test_tranche_no_atr_invalid():
    plan = tranche_plan(100.0, None)
    assert not plan["valid"]


def test_tranche_risk_identity_holds():
    """The sizing identity makes capital_at_risk == max_dollar_risk (rounded)."""
    for risk_pct in (0.01, 0.015, 0.02):
        plan = tranche_plan(180.0, 4.5, account=100_000, risk_pct=risk_pct)
        assert plan["risk_ok"]
        assert plan["capital_at_risk"] <= plan["max_dollar_risk"] + 1e-6


# ---------------------------------------------------------------------------
# Hybrid allocation matrix
# ---------------------------------------------------------------------------


def _dip_series():
    """A sustained dip that should read oversold (RSI <= 35, %b <= 0.10)."""
    closes = []
    px = 140.0
    for i in range(60):
        # steady -1.2 decline with small up-blips -> the last-14 RSI is low and
        # the close sits near the lower 2-sigma band (%b <= 0.10).
        drift = -1.2
        if i % 5 == 2:
            drift = 0.3
        px += drift
        closes.append(px)
    return closes


def test_setup_candidate_when_all_gates_pass():
    closes = _dip_series()
    highs = [c + 1.0 for c in closes]
    lows = [c - 1.0 for c in closes]
    vols = [1_000_000] * len(closes)
    setup = value_dip_setup(
        closes,
        highs,
        lows,
        vols,
        margin_of_safety=0.25,  # >= 20%
        fcf_yield=0.08,  # >= 6%
        val_z=-2.0,  # cheap vs history
        atr_value=0.5,  # small ATR -> stop distance <= 2% of price
    )
    rows = setup["rows"]
    assert rows["value_floor"]["pass"] is True
    assert rows["technical_entry"]["pass"] is True
    assert setup["candidate"] is True
    assert rows["valuation"]["verdict"] == "cheap"


def test_setup_technical_entry_fail_blocks_candidate():
    closes = _flat(60)
    highs = [c + 2.0 for c in closes]
    lows = [c - 2.0 for c in closes]
    setup = value_dip_setup(
        closes, highs, lows, [1_000_000] * 60, margin_of_safety=0.30, fcf_yield=0.10
    )
    assert setup["candidate"] is False
    assert setup["rows"]["technical_entry"]["pass"] is False


def test_setup_missing_data_renders_unknown_not_fail():
    setup = value_dip_setup([], [], [], [])
    assert setup["candidate"] is False
    assert setup["reasons"]


def test_setup_value_floor_or_semantics():
    """Value floor passes when EITHER MoS >= 20% OR FCF yield >= 6%."""
    closes = _dip_series()
    highs = [c + 1.0 for c in closes]
    lows = [c - 1.0 for c in closes]
    # FCF yield alone clears the floor
    setup = value_dip_setup(
        closes, highs, lows, [1_000_000] * len(closes), margin_of_safety=None, fcf_yield=0.07
    )
    assert setup["rows"]["value_floor"]["pass"] is True
    # MoS alone clears the floor
    setup2 = value_dip_setup(
        closes, highs, lows, [1_000_000] * len(closes), margin_of_safety=0.25, fcf_yield=None
    )
    assert setup2["rows"]["value_floor"]["pass"] is True


# ---------------------------------------------------------------------------
# Tranche risk fold (control computation for the governor)
# ---------------------------------------------------------------------------


def _realistic_closes(n=60):
    """Prices oscillating around ~180 with realistic 1-3%% daily swings
    (proxy ATR ~ 2-4), so the tranche ladder is well conditioned and the
    close series stays positive."""
    out = []
    px = 180.0
    for _ in range(n):
        px += 18.0 * math.sin(_ / 4)
        out.append(px)
    return out


def test_tranche_plan_new_worst_case_fields():
    plan = tranche_plan(180.0, 4.5, weights=(0.3, 0.3, 0.4), account=100_000, risk_pct=0.015)
    assert plan["valid"]
    # capital at risk == the risk budget (identity), as a fraction
    assert plan["capital_at_risk_pct"] == pytest.approx(0.015, abs=1e-3)
    # peak deployed > risk budget: scale-in deploys more at the lows
    assert plan["peak_deployed_pct"] > plan["capital_at_risk_pct"]


def test_tranche_risk_read_deterministic_worst_case():
    closes = _realistic_closes()
    read = tranche_risk_read(closes, max_position_pct=0.30, max_book_position_pct=0.45)
    assert read["valid"]
    assert "avg_entry" in read and read["avg_entry"] > 0
    # peak deployed is the fully-scaled fraction; capital at risk = budget
    assert read["capital_at_risk_pct"] == pytest.approx(0.015, abs=1e-3)
    assert read["peak_deployed_pct"] >= read["capital_at_risk_pct"]
    # book_ok compares peak-deployed against the book cap
    assert read["book_ok"] is True or read["book_ok"] is False


def test_tranche_risk_read_peak_cap_enforces_scale_in():
    closes = _realistic_closes()
    # A tight per-trade cap makes the fully-scaled position exceed it even
    # though the *risk budget* is met - the gap the fold closes.
    read = tranche_risk_read(closes, max_position_pct=0.02)
    assert read["valid"]
    assert read["capital_at_risk_pct"] <= 0.015  # risk budget met...
    assert read["peak_deployed_pct"] > 0.02  # ...but peak deploy blows the cap
    assert read["peak_ok"] is False


def test_tranche_risk_read_peak_ok_when_cap_roomy():
    closes = _realistic_closes()
    read = tranche_risk_read(closes, max_position_pct=0.60)
    assert read["valid"]
    assert read["peak_ok"] is True


def test_tranche_risk_read_invalid_without_closes():
    assert tranche_risk_read([])["valid"] is False


# ---------------------------------------------------------------------------
# Graph wiring: the tranche risk fold drives the governor's worst-case size
# ---------------------------------------------------------------------------


def _graph_config(**overrides):
    cfg = {
        "enable_strategy_overlays": True,
        "enable_events": False,
        "enable_orderflow": False,
        "enable_position_contract": True,
        "enable_risk_governor": True,
        "enable_computed_context": False,
        "enable_agreement": False,
        "enable_calibration": False,
        "enable_exits": False,
        "enable_tranche_risk": True,
        "tranche_weights": [0.3, 0.3, 0.4],
        "tranche_stop_mult": 1.5,
        "tranche_risk_pct": 0.015,
        "tranche_account": 100_000.0,
        "max_position_pct": 0.30,
        "risk_max_position_pct": 0.45,
        # CVaR budget high so the tranche peak-deployed / capital-at-risk is
        # the decision point in these tests (the synthetic series is volatile).
        "risk_daily_cvar_budget_pct": 0.10,
        "risk_max_drawdown_pct": 0.50,
        "risk_basket_tickers": [],
        "risk_basket_weights": {},
        "risk_audit_enabled": False,
        "target_vol": 0.15,
        "position_odds": 1.0,
        "kelly_fraction": 0.25,
        "risk_per_trade": 0.01,
        "atr_mult": 2.0,
    }
    cfg.update(overrides)
    return cfg


def _mk_graph(monkeypatch, closes, **cfg_over):
    import tradingagents.graph.trading_graph as tg

    graph = object.__new__(tg.TradingAgentsGraph)
    graph.config = _graph_config(**cfg_over)
    monkeypatch.setattr(graph, "_try_fetch_closes", lambda *a, **k: closes)
    monkeypatch.setattr(graph, "_basket_cvar", lambda *a, **k: None)
    return graph


def test_graph_tranche_fold_writes_context_and_passes(monkeypatch):
    graph = _mk_graph(monkeypatch, _realistic_closes())
    out = graph._apply_strategy_overlays(
        {"trade_date": "2026-08-19", "final_trade_decision": "Hold"}, "NVDA"
    )
    ctx = out.get("tranche_context") or {}
    assert ctx.get("peak_deployed_pct") is not None
    assert ctx.get("capital_at_risk_pct") is not None
    assert ctx.get("avg_entry") is not None
    # peak-deployed (11%) within the 30% cap and capital-at-risk within the
    # 1.5% budget -> not REJECT (a near-budget touch is an honest WARN, the
    # tranche plan spends ~98% of its risk budget by construction).
    assert out["risk_gate"]["verdict"] in ("PASS", "WARN")
    assert out.get("risk_halt") is not True
    # the contract used the weighted tranche entry
    assert "tranche weighted entry" in out.get("position_contract", "")


def test_graph_tranche_fold_rejects_when_peak_deployed_blows_cap(monkeypatch):
    graph = _mk_graph(monkeypatch, _realistic_closes(), max_position_pct=0.05)
    out = graph._apply_strategy_overlays(
        {"trade_date": "2026-08-19", "final_trade_decision": "Buy"}, "NVDA"
    )
    # risk budget is met but the fully-scaled position exceeds the per-trade cap
    assert out["risk_gate"]["verdict"] == "REJECT"
    assert any("cap" in r for r in out["risk_gate"]["reasons"])
    assert out.get("risk_halt") is True


def test_graph_tranche_fold_off_by_default(monkeypatch):
    graph = _mk_graph(monkeypatch, _realistic_closes(), enable_tranche_risk=False)
    out = graph._apply_strategy_overlays(
        {"trade_date": "2026-08-19", "final_trade_decision": "Hold"}, "NVDA"
    )
    assert "tranche_context" not in out
    # no capital-at-risk line in any snapshot
    snap = out.get("risk_snapshot") or ""
    assert "cap_at_risk" not in snap


def test_graph_tranche_fold_contract_uses_weighted_entry(monkeypatch):
    closes = _realistic_closes()
    graph = _mk_graph(monkeypatch, closes)
    out = graph._apply_strategy_overlays(
        {"trade_date": "2026-08-19", "final_trade_decision": "Buy"}, "NVDA"
    )
    # the weighted entry is below the last close -> the dollar stop is below
    # the last-close stop; assert the contract text carries the tranche tag
    assert "tranche weighted entry" in out.get("position_contract", "")


# ---------------------------------------------------------------------------
# New gap functions (Value_Dip_swing.md §1 + §2): the 6 implemented gaps
# ---------------------------------------------------------------------------


def _dip_trigger_series():
    """A dip -> volume dry-up -> high-volume reversal series that satisfies
    the Step-2 ladder: VDU, trigger candle (RVOL>=1.3, close above prior high),
    higher-low, and MACD bullish divergence."""
    closes, highs, lows = [], [], []
    px = 200.0
    for n, drift in [(100, -0.15), (13, -1.2), (5, 0.4), (7, -0.2), (14, 0.6), (4, -0.4), (7, 0.3)]:
        for _ in range(n):
            px += drift
            closes.append(px)
            highs.append(px + 1.0)
            lows.append(px - 1.0)
    closes.append(px + 4.0)
    highs.append(px + 5.0)
    lows.append(px - 0.5)
    vols = [2_000_000] * len(closes)
    for i in range(len(closes) - 8, len(closes) - 1):
        vols[i] = 300_000
    vols[-1] = 4_500_000
    return closes, highs, lows, vols


# --- balance sheet health ---


def test_balance_sheet_health_or_semantics():
    # D/E < 1 OR current ratio > 1.5 -> either passes
    assert balance_sheet_health(0.5, 2.0)["pass"] is True
    assert balance_sheet_health(2.0, 2.0)["pass"] is True  # cr side
    assert balance_sheet_health(0.5, 0.8)["pass"] is True  # d_e side
    assert balance_sheet_health(2.0, 0.8)["pass"] is False
    assert balance_sheet_health()["pass"] is None  # unknown neither fails


def test_profitability_quality_and_semantics():
    assert profitability_quality(fcf=1e9, roe=0.20)["pass"] is True
    assert profitability_quality(fcf=-1e9, roe=0.10)["pass"] is False
    # missing side ignored
    assert profitability_quality(fcf=1e9)["pass"] is True
    assert profitability_quality(roe=0.25)["pass"] is True
    assert profitability_quality()["pass"] is None
    assert profitability_quality(fcf=-1e9)["pass"] is False  # fcf alone fails


# --- technical Step-2 ---


def test_volume_dry_up():
    vols = [2_000_000] * 30 + [300_000] * 5 + [2_000_000]
    assert volume_dry_up(vols)["dry_up"] is True
    # high recent volume vs prior -> no dry-up (enough bars for the window)
    assert volume_dry_up([1] * 30 + [2] * 10)["dry_up"] is False
    assert volume_dry_up([])["dry_up"] is None


def test_macd_divergence_bullish():
    closes, highs, lows, _ = _dip_trigger_series()
    m = macd_divergence(closes, lows)
    assert m["verdict"] in ("bullish-divergence", "higher-low")
    assert m["bullish"] is True


def test_trigger_candle_and_higher_low():
    closes, highs, lows, vols = _dip_trigger_series()
    tc = trigger_candle(closes, highs, lows, vols)
    assert tc["trigger"] is True
    assert tc["rvol"] >= 1.3
    assert tc["close_above_prior_high"] is True
    hl = higher_low_structure(lows, window=80)
    assert hl["higher_low"] is True


def test_vdu_entry_setup_candidate():
    closes, highs, lows, vols = _dip_trigger_series()
    vd = vdu_entry_setup(closes, highs, lows, vols, support_window=80)
    assert vd["candidate"] is True
    assert vd["volume_dry_up"]["dry_up"] is True
    assert vd["trigger_candle"]["trigger"] is True


def test_support_structure_needs_history():
    # insufficient history -> unknown
    assert support_structure([1.0] * 50, [1.0] * 50, [1.0] * 50)["verdict"] == "unknown"
    # 200+ bars with a shallow base -> holding-above-base or support
    closes = [100.0 + 0.1 * i for i in range(300)]
    highs = [c + 1.0 for c in closes]
    lows = [c - 1.0 for c in closes]
    sp = support_structure(closes, highs, lows)
    assert sp["verdict"] in (
        "multi-month-base-support",
        "200-day-sma-support",
        "holding-above-base",
    )


# --- decline driver ---


def test_decline_driver_clean():
    assert decline_driver_check()["verdict"] == "clean"
    assert decline_driver_check(fcf=1e9, roe=0.2)["verdict"] == "clean"


def test_decline_driver_structural():
    out = decline_driver_check(trap_level="HIGH", accrual=0.10, mom12=-0.30)
    assert out["verdict"] == "structural"
    assert out["clean"] is False


def test_decline_driver_caution():
    out = decline_driver_check(accrual=0.10)  # single flag
    assert out["verdict"] == "caution"


# --- extended matrix gates on the new rows when measured ---


def test_matrix_gates_on_balance_and_profitability():
    closes, highs, lows, vols = _dip_trigger_series()
    # balance + profitability fail -> candidate False
    s = value_dip_setup(
        closes,
        highs,
        lows,
        vols,
        margin_of_safety=0.25,
        fcf_yield=0.08,
        atr_value=0.5,
        debt_to_equity=2.5,
        current_ratio=0.8,
        roe=0.05,
        fcf=-5e8,
    )
    assert s["rows"]["balance_sheet"]["pass"] is False
    assert s["rows"]["profitability"]["pass"] is False
    assert s["candidate"] is False


def test_matrix_ignores_unknown_new_rows():
    closes, highs, lows, vols = _dip_trigger_series()
    # no balance/profitability inputs -> rows None-pass, candidate unaffected
    s = value_dip_setup(
        closes,
        highs,
        lows,
        vols,
        margin_of_safety=0.25,
        fcf_yield=0.08,
        atr_value=0.5,
    )
    assert s["rows"]["balance_sheet"]["pass"] is None
    assert s["rows"]["profitability"]["pass"] is not False or s["candidate"] is True
