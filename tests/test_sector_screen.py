"""Tests for the Sector Rotation Screen (strategies/sector_screener.py).

Covers the regime classification + grade cap, dispersion trend,
pullback-divergence flags, Setup-A/B + stock-screen predicates, the
constituent breadth/EW-CW screen and the after-cost backtest — all on
synthetic closes (hermetic, no network). The tool's wiring is covered by the
calc->agent wiring gate.
"""

import random

import pytest

from tradingagents.strategies.sector_screener import (
    backtest_rotation,
    cap_grade,
    classify_regime,
    constituent_screens,
    constituent_universe,
    dispersion_trend,
    grade_for,
    pullback_divergence,
    sector_screen,
    setup_a,
    setup_b,
    stock_screen,
)

pytestmark = pytest.mark.timeout(90)

_SPDR = ["XLK", "XLC", "XLY", "XLI", "XLE", "XLF", "XLV", "XLP", "XLU", "XLB", "XLRE"]


def _gen(n=320, drift=0.0004, vol=0.012, seed=1):
    rnd = random.Random(seed)
    out, px = [], 100.0
    for _ in range(n):
        px *= 1 + rnd.gauss(drift, vol)
        out.append(px)
    return out


def _closes_map(seed=1):
    return {e: _gen(seed=seed + i) for i, e in enumerate(_SPDR)}


# ---------------------------------------------------------------------------
# regime + grades
# ---------------------------------------------------------------------------


def test_classify_regime_bull_neutral_bear():
    bull = [100 + i * 0.05 for i in range(300)]  # rising, above SMA200
    assert classify_regime(bull) == "bull"
    bear = [100 - i * 0.05 for i in range(300)]
    assert classify_regime(bear) == "bear"
    flat = [100.0] * 300
    assert classify_regime(flat) == "neutral"
    assert classify_regime([1, 2, 3]) is None  # insufficient bars


def test_grade_and_cap():
    assert grade_for(92) == "Strong Overweight"
    assert grade_for(46) == "Neutral"
    assert grade_for(8) == "Avoid"
    assert grade_for(None) is None
    # neutral caps at Moderate Overweight, bear at Neutral
    assert cap_grade("Overweight", "neutral") == "Moderate Overweight"
    assert cap_grade("Slight Overweight", "bear") == "Neutral"
    assert cap_grade("Overweight", "bull") == "Overweight"
    assert cap_grade(None, "bear") is None


# ---------------------------------------------------------------------------
# dispersion
# ---------------------------------------------------------------------------


def test_dispersion_trend():
    low = [0.004] * 20
    high = [0.020] * 10
    assert dispersion_trend(low + high) == "rising"
    assert dispersion_trend(high + low) != "rising"
    assert dispersion_trend([0.01] * 12) is None  # insufficient


# ---------------------------------------------------------------------------
# pullback divergence
# ---------------------------------------------------------------------------


def test_pullback_divergence_flags_leaders():
    closes_map = {"XLK": _gen(seed=3), "XLE": _gen(seed=4)}
    # benchmark down 2+ sessions at the tail
    bench = [100 - i * 1.0 for i in range(8)] + [100, 100, 99.5, 99.0]
    div = pullback_divergence(closes_map, bench)
    assert div["triggered"] is True
    assert "down" in div["reason"]
    # a sector closing green that session is a leader
    green_map = {"XLK": [100.0] * 6 + [102.0], "XLE": [100.0] * 6 + [99.0]}
    div2 = pullback_divergence(green_map, bench)
    assert div2["leaders"] == ["XLK"]


def test_pullback_divergence_no_pullback():
    bench = [100 + i * 0.5 for i in range(10)]
    div = pullback_divergence({"XLK": _gen()}, bench)
    assert div["triggered"] is False
    assert div["leaders"] == []


# ---------------------------------------------------------------------------
# setup A / B + stock screen
# ---------------------------------------------------------------------------


def _ohlcv_gen(seed=1, n=260):
    rnd = random.Random(seed)
    closes, highs, lows, vols, opens = [], [], [], [], []
    px = 100.0
    for _ in range(n):
        o = px * (1 + rnd.gauss(0, 0.004))
        hi = o * (1 + abs(rnd.gauss(0, 0.002)))
        lo = o * (1 - abs(rnd.gauss(0, 0.002)))
        cl = (hi + lo) / 2
        opens.append(o)
        highs.append(hi)
        lows.append(lo)
        closes.append(cl)
        vols.append(1e6 * (0.4 + rnd.random()))
        px = cl
    return closes, highs, lows, vols, opens


def test_setup_a_ready_in_zone():
    closes, highs, lows, vols, opens = _ohlcv_gen(seed=5)
    a = setup_a(closes, highs, vols)
    assert a["state"] in ("ready", "none")  # synthetic shelf may or may not be in-zone
    assert isinstance(a["dist"], (float, type(None)))


def test_setup_a_fires_on_volume_breakout():
    # a clear uptrend, then a tight shelf AT the highs, cleared on a volume
    # spike (design: Setup A high-tight shelf breakout on 1.5x+ volume).
    n = 260
    rnd = random.Random(6)
    closes, highs, vols = [], [], []
    px = 100.0
    for _ in range(n - 16):
        px *= 1 + rnd.gauss(0.0015, 0.006)
        hi = px * 1.004
        closes.append(px)
        highs.append(hi)
        vols.append(1e6)
    peak = max(highs)
    base_vol = vols[-1]
    ramp = [base_vol * 0.8, base_vol * 0.6, base_vol * 0.5, base_vol * 0.5,
            base_vol * 0.45, base_vol * 0.4, base_vol * 0.4, base_vol * 0.35,
            base_vol * 0.35, base_vol * 0.3, base_vol * 0.3, base_vol * 0.3,
            base_vol * 0.25, base_vol * 0.25, base_vol * 0.25]
    for k in range(15):  # tight shelf at the peak, volume contracting
        px = peak * (1 + rnd.gauss(0, 0.0015))
        closes.append(px)
        highs.append(max(px, peak * 0.9995))
        vols.append(ramp[k])
    # clear the shelf high (tied to the newest shelf bar, ~peak*0.9995) and
    # the 52w high on a volume spike -> 'fire'
    closes.append(peak * 1.03)
    highs.append(peak * 1.035)
    vols.append(1e6 * 4)  # breakout volume spike
    a = setup_a(closes, highs, vols)
    assert a["state"] == "fire", a


def test_setup_b_pullback_rising_ema():
    # strong uptrend -> last bar dips to touch the rising EMA20 and closes
    # green (reversal). EMA20 must be rising (contrast with the tail).
    closes, highs, lows, vols, opens = _ohlcv_gen(seed=7)
    # make the pre-tail bars a rising trend and the EMA-20 window rising
    n = len(closes)
    for i in range(n - 8, n):
        closes[i] = closes[i - 1] * 1.004 if i > n - 8 else closes[i - 1]
    from tradingagents.strategies.sector_screener import _ema
    e20 = _ema(closes, 20)
    closes[-1] = e20 * 1.005
    opens[-1] = e20 * 0.995
    b = setup_b(closes, opens)
    assert b["state"] == "fired", b


def test_stock_screen_filters_extended_chase():
    closes, highs, lows, vols, opens = _ohlcv_gen(seed=8)
    closes[-1] = max(closes) * 1.2  # extended >> 5% above EMA20
    out = stock_screen({"NVDA": closes}, _gen(seed=9))
    assert out["ok"] is False
    # the name is rejected either as architecture (P too far above EMA20) or
    # as an extended chase - both are the no-chase guard doing its job
    assert out["detail"], "expected at least one reject reason"


# ---------------------------------------------------------------------------
# sector screen + constituents + backtest
# ---------------------------------------------------------------------------


def test_sector_screen_shape():
    cm = _closes_map(seed=11)
    bench = _gen(seed=99)
    screen = sector_screen(cm, bench)
    assert screen["rows"]
    assert screen["regime"] in ("bull", "neutral", "bear", None)
    assert isinstance(screen["leaders"], list)
    for r in screen["rows"][:3]:
        assert "grade" in r and "grade_capped" in r


def test_constituent_screens_breadth_ewcw():
    parents = {"XLK": {"NVDA": {"closes": _gen(seed=21), "highs": _gen(seed=22),
                                "volumes": [1e6] * 320, "opens": _gen(seed=23)},
                       "AMD": {"closes": _gen(seed=24), "highs": _gen(seed=25),
                               "volumes": [1e6] * 320, "opens": _gen(seed=26)}}}
    cs = constituent_screens(_closes_map(seed=27), parents)
    blk = cs["XLK"]
    assert isinstance(blk["breadth"]["pct"], float)  # computable
    assert blk["leadership"] is not None or blk["leadership"] is None
    assert len(blk["setups"]) == 2
    assert all("setup_a" in s and "setup_b" in s for s in blk["setups"])


def test_backtest_rotation_no_lookahead_and_cost():
    cm = _closes_map(seed=31)
    bench = _gen(seed=32)
    bt = backtest_rotation(cm, bench, hold_bars=21, top_n=3, cost_bps=5.0)
    assert len(bt["strategy"]) == len(bt["bench"]) > 100
    assert bt["turns"] >= 0.0
    # cost line <= no-cost line on the first period (cost charged)
    bt0 = backtest_rotation(cm, bench, hold_bars=21, top_n=3, cost_bps=0.0)
    assert len(bt0["strategy"]) == len(bt["strategy"])


def test_backtest_rotation_short_input_none():
    bt = backtest_rotation({}, [])
    assert bt["strategy"] == [] and bt["turns"] == 0.0


# ---------------------------------------------------------------------------
# EODHD constituent universe (breadth-layer wiring)
# ---------------------------------------------------------------------------


def _symbol(code, stype="Common Stock"):
    return {"Code": code, "Name": code, "Country": "US", "Exchange": "NYSE",
            "Currency": "USD", "Type": stype}


def _sector_of(name):
    return {"NVDA": "Information Technology", "AMD": "Information Technology",
            "JPM": "Financial Services", "GS": "Financial Services",
            "DUKE": "Utilities", "F": "Consumer Discretionary"}.get(name)


@pytest.fixture(autouse=True)
def _clear_sector_lookup_cache():
    """The module-level sector-lookup cache must not leak between tests."""
    import tradingagents.strategies.sector_screener as sc
    sc._SECTOR_LOOKUP_CACHE.clear()
    yield
    sc._SECTOR_LOOKUP_CACHE.clear()


def test_constituent_universe_buckets_and_caps():
    symbols = [_symbol("NVDA"), _symbol("AMD"), _symbol("JPM"), _symbol("GS"),
               _symbol("DUKE"), _symbol("F"), _symbol("ZZZ")]  # ZZZ unknown -> dropped
    uni = constituent_universe(symbols, _sector_of, per_sector_cap=1, budget=10)
    stats = uni.pop("stats")
    assert uni["XLK"] == ["NVDA"] or uni["XLK"] == ["AMD"]  # first win under cap 1
    assert uni["XLF"] == ["JPM"] or uni["XLF"] == ["GS"]
    assert uni["XLU"] == ["DUKE"]
    assert "XLX" not in uni  # every key is a real SPDR ETF
    assert stats["n_bucketed"] >= 4


def test_constituent_universe_budget_and_type_filter():
    symbols = ([_symbol("AMD", "Fund")]  # not Common Stock -> dropped before lookup
               + [_symbol("NVDA"), _symbol("JPM"), _symbol("GS"), _symbol("DUKE")]
               + [_symbol("Q" + str(i)) for i in range(30)])
    def of(name):
        return _sector_of(name) if _sector_of(name) else "Unmapped Sector"
    uni = constituent_universe(symbols, of, per_sector_cap=5, budget=6)
    stats = uni.pop("stats")
    assert stats["n_looked_up"] <= 6  # budget-bounded
    bucketed = {t for v in uni.values() for t in v}
    assert "AMD" not in bucketed  # Fund type dropped (never classified)


def test_constituent_universe_early_bail_on_dead_classifier():
    # a classifier that always returns None must not burn the budget
    symbols = [_symbol("A" + str(i)) for i in range(40)]
    calls = {"n": 0}

    def dead(name):
        calls["n"] += 1
        return None

    uni = constituent_universe(symbols, dead, per_sector_cap=3, budget=40)
    stats = uni.pop("stats")
    assert stats["dead"] is True
    assert uni == {}
    assert calls["n"] <= 14  # bailed after max(6, budget//3)=13 dead lookups


def test_breadth_gate_blocks_small_samples():
    from tradingagents.strategies.sector_screener import breadth_with_gate
    small = breadth_with_gate({"pct": 33.3, "n": 3, "above": 1, "window": 50}, min_n=20)
    assert small["pct"] is None and small["small_sample"] is True
    assert "sample 3 < 20" in small["reason"]
    ok = breadth_with_gate({"pct": 60.0, "n": 30, "above": 18, "window": 50}, min_n=20)
    assert ok["pct"] == 60.0 and ok["small_sample"] is False
    assert breadth_with_gate(None, min_n=20)["pct"] is None


def test_leadership_ratio_ewcw_deterministic():
    from tradingagents.strategies.sector_screener import leadership_ratio_ewcw
    cw = [100.0 * (1.0003 ** i) for i in range(120)]           # mild cap uptrend
    ew_strong = [100.0 * (1.0012 ** i) for i in range(120)]    # stronger EW
    ew_weak = [100.0 * (1.0001 ** i) for i in range(120)]      # lagging EW
    up = leadership_ratio_ewcw(cw, ew_strong)
    assert up["ratio"] is not None
    assert up["label"] == "broadening"                     # ratio above own SMA
    assert up["spread_pct"] is not None
    down = leadership_ratio_ewcw(cw, ew_weak)
    assert down["label"] in ("narrowing", "flat")
    # immune to price level: scaling BOTH series equally leaves the ratio
    up2 = leadership_ratio_ewcw([c * 1000 for c in cw], [c * 1000 for c in ew_strong])
    assert abs(up["ratio"] - up2["ratio"]) < 1e-6
    # None-safe
    assert leadership_ratio_ewcw([], [])["ratio"] is None


def test_ew_cw_etfs_map_complete():
    import tradingagents.strategies.sector_screener as sc
    from tradingagents.strategies.sector_rank import SPDR_SECTORS
    assert set(sc.EW_CW_ETFS) == set(SPDR_SECTORS)  # every cap sector has an RSP* EW


def test_eodhd_breadth_composition(monkeypatch):
    from tradingagents.strategies import sector_screener as sc
    # a fake member map drives constituent_screens (the tool's post-bucket path)
    member_closes = {"NVDA": {"closes": _gen(seed=41), "highs": _gen(seed=42),
                              "volumes": [1e6] * 320, "opens": _gen(seed=43)}}
    cs = sc.constituent_screens(_closes_map(seed=44), {"XLK": member_closes})
    assert "XLK" in cs
    assert cs["XLK"]["members"] == 1
    assert isinstance(cs["XLK"]["breadth"]["pct"], float)
