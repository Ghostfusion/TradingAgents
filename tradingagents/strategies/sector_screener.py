"""Sector Rotation Screen (design: docs/design_sector_rotation_screener.md).

A **sector-first** screen — early leader identification — composed from the
existing rotation machinery (``sector_rank`` multifactor rank + RRG quadrant)
rather than a second implementation. Every function here is **pure, advisory,
None-safe**: a missing series renders n/a, never fabricated; no signal is a
gate (the repo's risk governor / regime gate remain authoritative).

Pipeline: REGIME (SPY trend + dispersion) -> SECTOR RANK (RS/momentum
multifactor + quadrant) -> PULLBACK-DIVERGENCE leader flags ->
(constituent screens when enabled) BREADTH / EW-CW leadership ->
STOCK SETUP A/B inside the leaders -> (notes only; no auto-execution).

The constituent-heavy parts (breadth / EW-CW / Setup A/B) are gated by
``enable_sector_breadth`` upstream in the tool (default off), matching
``get_sector_rank``'s gate convention — the P1 sector screen always renders.
"""

from __future__ import annotations

import statistics

from .sector_rank import (
    constituent_breadth,
    leadership_ratio,
    rank_sectors_multifactor,
)

# Canonical cap-weight -> equal-weight sector ETF pairs (Invesco RSP-linked
# sector ETFs, current tickers as of 2026-06). These are the REAL S&P-500
# equal-weight sector indices, so EW/CW reads are sample-independent and
# comparable across sectors (the fix for the micro-sample ratio).
EW_CW_ETFS: dict[str, str] = {
    "XLK": "RSPT",
    "XLF": "RSPF",
    "XLV": "RSPH",
    "XLY": "RSPD",
    "XLI": "RSPN",
    "XLB": "RSPM",
    "XLE": "RSPG",
    "XLU": "RSPU",
    "XLC": "RSPC",
    "XLRE": "RSPR",
    "XLP": "RSPS",
}


# Sector screen defaults (design doc §5).
_REQUIRE_BARS = 65
_DEFAULT_TOP_N = 5
_GRADE_BANDS = (
    (90, "Strong Overweight"),
    (80, "Overweight"),
    (70, "Moderate Overweight"),
    (60, "Slight Overweight"),
    (45, "Neutral"),
    (35, "Slight Underweight"),
    (25, "Underweight"),
    (10, "Strong Underweight"),
    (0, "Avoid"),
)
_CAP_FLOOR = {"neutral": 70.0, "bear": 45.0}  # regime -> max grade-band floor

# Setup-A / Setup-B predicate defaults (doc §5.2).
_SHELF_W = 15
_HI_W = 252
_VOL_W = 20
_TOUCH_TOL = 0.02


def _sma_last(values: list, window: int) -> float | None:
    """Last value of a simple moving average (None-safe)."""
    if not values or window <= 0 or len(values) < window:
        return None
    window = min(window, len(values))
    return sum(values[-window:]) / window


def _ema(values: list, window: int) -> float | None:
    """Last value of an exponential moving average (None-safe)."""
    if not values or window <= 0:
        return None
    k = 2.0 / (window + 1)
    e = values[0]
    for v in values[1:]:
        e = k * v + (1 - k) * e
    return e


def _mean(values: list) -> float | None:
    vals = [v for v in values if v is not None]
    return sum(vals) / len(vals) if vals else None


def _daily_returns(closes: list) -> list:
    if not closes or len(closes) < 2:
        return []
    return [closes[i] / closes[i - 1] - 1.0 for i in range(1, len(closes))
            if closes[i] is not None and closes[i - 1]]


# ---------------------------------------------------------------------------
# regime classification (doc §3.1: SPY > SMA200 with rising slope -> bull;
# below with falling slope -> bear; else neutral) and the grade cap table.
# ---------------------------------------------------------------------------


def classify_regime(closes: list, *, sma_w: int = 200, slope_bars: int = 20) -> str | None:
    """'bull' | 'neutral' | 'bear' | None (insufficient bars)."""
    if not closes or len(closes) < sma_w + slope_bars:
        return None
    sma = _sma_last(closes, sma_w)
    early = _sma_last(closes[:-slope_bars], sma_w)
    if sma is None or early is None:
        return None
    slope = sma - early
    if closes[-1] > sma and slope > 0:
        return "bull"
    if closes[-1] < sma and slope < 0:
        return "bear"
    return "neutral"


def grade_for(score: float | None) -> str | None:
    """Grade band for a 0-100 score (doc §5 table). None-safe."""
    if score is None:
        return None
    for floor, label in _GRADE_BANDS:
        if score >= floor:
            return label
    return _GRADE_BANDS[-1][1]


def cap_grade(grade: str | None, regime: str | None) -> str | None:
    """Regime cap on the grade: bull uncapped; neutral caps at Moderate
    Overweight; bear caps at Neutral. Unknown regime uncapped. None-safe."""
    if grade is None or regime not in ("neutral", "bear"):
        return grade
    cur_floor = next((f for f, label in _GRADE_BANDS if grade == label), None)
    cap_floor = _CAP_FLOOR[regime]
    if cur_floor is not None and cur_floor > cap_floor:
        return next((label for f, label in _GRADE_BANDS if f == cap_floor), grade)
    return grade


# ---------------------------------------------------------------------------
# dispersion (rotation-regime context line)
# ---------------------------------------------------------------------------


def dispersion_series(closes_map: dict) -> list:
    """Daily cross-sectional stdev across the sector ETFs' returns (aligned)."""
    series = [_daily_returns(c) for c in (closes_map or {}).values() if c]
    series = [s for s in series if s]
    if not series:
        return []
    n = min(len(s) for s in series)
    return [round(statistics.pstdev([s[i] for s in series]), 6) for i in range(n)]


def dispersion_trend(series: list, *, recent_w: int = 5, prior_w: int = 15) -> str | None:
    """'rising' | 'falling' | 'flat' | None — rotation-regime context."""
    if not series or len(series) < recent_w + prior_w:
        return None
    recent = _mean(series[-recent_w:])
    prior = _mean(series[-(recent_w + prior_w):-recent_w])
    if recent is None or prior is None:
        return None
    if recent > prior * 1.05:
        return "rising"
    if recent < prior * 0.95:
        return "falling"
    return "flat"


# ---------------------------------------------------------------------------
# pullback divergence (doc §5.1): SPY down 2+ sessions or undercutting a
# recent swing low -> flag sectors closing green or holding above the prior
# day's high (early rotation leaders). Practitioner evidence: flag only.
# ``highs_map`` optional; without it "holding" degrades to holding the prior
# close level (honest, stated in the reason).
# ---------------------------------------------------------------------------


def pullback_divergence(closes_map: dict, bench_closes: list,
                        highs_map: dict | None = None, *,
                        lookback: int = 6) -> dict:
    """{'triggered', 'reason', 'leaders', 'here'}."""
    out = {"triggered": False, "reason": "", "leaders": [], "n": 0}
    if not bench_closes or len(bench_closes) < 3:
        out["reason"] = "no benchmark series"
        return out
    tail = bench_closes[-(lookback + 1):]
    streak = 0
    for a, b in zip(tail[:-1], tail[1:], strict=False):
        streak = streak + 1 if b < a else 0
    window = bench_closes[-(len(tail) + 1):-1]
    undercut = bool(window) and bench_closes[-1] < min(window)
    if streak >= 2:
        out["triggered"], out["reason"] = True, f"benchmark down {streak}+ sessions"
    elif undercut:
        out["triggered"], out["reason"] = True, "benchmark undercut a recent swing low"
    if not out["triggered"]:
        out["reason"] = "no pullback"
        return out
    leaders = []
    for etf, closes in (closes_map or {}).items():
        if not closes or len(closes) < 2:
            continue
        green = closes[-1] > closes[-2]
        highs = (highs_map or {}).get(etf) or []
        holding = bool(highs) and len(highs) >= 2 and highs[-1] >= highs[-2]
        if green or holding:
            leaders.append(etf)
    out["leaders"] = leaders
    out["n"] = len(leaders)
    return out


# ---------------------------------------------------------------------------
# stock-layer predicates (design §5.2): Setup A high-tight shelf, Setup B
# first pullback to a rising 20d EMA. All OHLCV-list inputs, all None-safe.
# ---------------------------------------------------------------------------


def _architecture(closes: list) -> dict:
    """P > EMA20 > SMA50 > SMA200; {'ok': bool, 'detail': [str]}."""
    if not closes or len(closes) < 200:
        return {"ok": False, "detail": ["< 200 bars"]}
    p = closes[-1]
    e20 = _ema(closes, 20)
    s50 = _sma_last(closes, 50)
    s200 = _sma_last(closes, 200)
    if not (e20 and s50 and s200):
        return {"ok": False, "detail": ["incomplete MAs"]}
    detail = []
    if not p > e20:
        detail.append("P <= EMA20")
    if not e20 > s50:
        detail.append("EMA20 <= SMA50")
    if not s50 > s200:
        detail.append("SMA50 <= SMA200")
    return {"ok": not detail, "detail": detail or ["aligned"]}


def _rel_outperformance(closes: list, sector_closes: list, *, w: int = 20) -> float | None:
    """20d stock return minus the sector ETF's 20d return (>= +2% = leader)."""

    def r20(c: list) -> float | None:
        if not c or len(c) < w + 1:
            return None
        return c[-1] / c[-(w + 1)] - 1.0

    s, sec = r20(closes), r20(sector_closes)
    if s is None or sec is None:
        return None
    return round(s - sec, 4)


def _no_chase(closes: list, *, tol: float = 0.05) -> bool | None:
    """False when extended > tol above the 20d EMA (no extended chase)."""
    e20 = _ema(closes, 20)
    if e20 is None or not closes:
        return None
    return (closes[-1] / e20 - 1.0) <= tol


def setup_a(closes: list, highs: list | None = None, volumes: list | None = None, *,
            shelf_w: int = _SHELF_W, hi_w: int = _HI_W, vol_w: int = _VOL_W) -> dict:
    """High-tight shelf (3-6% of the 52-week high) + volume contraction.

    Returns ``{'state': 'fire'|'ready'|'none', 'dist', 'reasons'}``:
    ``fire`` = shelf high cleared on >= 1.5x avg volume; ``ready`` =
    consolidating in the zone and not yet cleared; ``none`` otherwise.
    """
    hi = list(highs or [])
    vols = list(volumes or [])
    out = {"state": "none", "dist": None, "reasons": []}
    if not closes or len(closes) < 2:
        out["reasons"].append("< 2 bars")
        return out
    hi52 = max(hi[-hi_w:]) if hi else max(closes)
    shelf = hi[-(shelf_w + 1):-1] if len(hi) > shelf_w else (hi[-shelf_w:] if hi else [])
    shelf_high = max(shelf) if shelf else closes[-1]
    if shelf_high < hi52 * 0.94:
        out["reasons"].append("shelf below the 52w-high zone")
        return out
    shelf_low = min(hi[-(shelf_w + 1):-1]) if len(hi) > shelf_w else (min(hi[-shelf_w:]) if hi else closes[-1])
    price = closes[-1]
    if shelf_high - shelf_low > 0.10 * price:
        out["reasons"].append("range too wide for a tight shelf")
    v20 = _mean(vols[-vol_w:]) if len(vols) >= vol_w else None
    v_shelf = _mean(vols[-shelf_w:]) if len(vols) >= shelf_w else None
    pre_shelf = vols[-(shelf_w + vol_w):-shelf_w] if len(vols) >= shelf_w + vol_w else vols[:-shelf_w]
    v_pre = _mean(pre_shelf) if pre_shelf else None
    if v_pre and v_shelf is not None and v_shelf > 0.75 * v_pre:
        out["reasons"].append("volume not contracting (shelf <= 75% pre-shelf avg)")
    if len(out["reasons"]) > 1:
        return out
    cleared = price >= shelf_high
    fired_vol = bool(vols) and vols[-1] is not None and v20 is not None and vols[-1] >= 1.5 * v20
    if cleared and fired_vol:
        return {"state": "fire", "dist": 0.0, "reasons": ["cleared the shelf on 1.5x+ volume"]}
    if cleared:
        return {"state": "none", "dist": 0.0, "reasons": ["cleared the shelf without volume"]}
    return {"state": "ready", "dist": round(max(0.0, shelf_high - price), 4),
            "reasons": ["shelf in zone, volume contracting"] if not out["reasons"] else out["reasons"]}


def setup_b(closes: list, opens: list | None = None, *, ema_w: int = 20,
            touch_tol: float = _TOUCH_TOL) -> dict:
    """First pullback to a RISING 20d EMA + reversal candle (mean-reversion)."""
    out = {"state": "none", "dist": None, "reasons": []}
    if not closes or len(closes) < ema_w + 6:
        out["reasons"].append("insufficient bars")
        return out
    e20 = _ema(closes, 20)
    prior_ema = _ema(closes[:-6], 20)
    if e20 is None:
        out["reasons"].append("no EMA20")
        return out
    rising = prior_ema is not None and e20 > prior_ema
    if not rising:
        out["reasons"].append("EMA20 not rising")
    touched = min(closes[-2:]) <= e20 * (1 + touch_tol)
    if not touched:
        out["reasons"].append("no EMA20 touch")
    recovered = closes[-1] >= e20
    green = bool(opens) and len(opens) >= 2 and opens[-1] is not None and closes[-1] > opens[-1]
    if not green and opens:
        out["reasons"].append("reversal candle missing")
    if rising and touched and recovered and (green or not opens):
        return {"state": "fired",
                "dist": round(max(0.0, e20 - min(closes[-2:])), 4),
                "reasons": ["pullback to rising EMA20 + reversal candle"]}
    return out


def stock_screen(closes: dict, sector_closes: list, *, min_bars: int = 200) -> dict:
    """Per-name stock screen inside a leader sector (design §5.2): the
    architecture / relative-outperformance / no-chase filters, with the
    Setup-A/B states attached. None-safe; unknown -> n/a fields."""
    name = list(closes)[0] if closes else "?"
    c = closes.get(name) or []
    out = {"ticker": name, "ok": False, "detail": [], "setup_a": None, "setup_b": None}
    if len(c) < min_bars:
        out["detail"].append("< 200 bars")
        return out
    arch = _architecture(c)
    if not arch["ok"]:
        out["detail"].extend(arch["detail"])
        return out
    rel = _rel_outperformance(c, sector_closes)
    if rel is not None and rel < 0.02:
        out["detail"].append(f"20d vs sector {rel:+.2%} < +2% (beta-rider)")
        return out
    if _no_chase(c) is False:
        out["detail"].append("extended > +5% above EMA20 (no chase)")
        return out
    out["ok"] = True
    out["detail"] = ["aligned", f"rel {rel:+.1%}" if rel is not None else "rel n/a"]
    return out


# ---------------------------------------------------------------------------
# top-level screen builders
# ---------------------------------------------------------------------------


def sector_screen(
    closes_map: dict,
    bench_closes: list | None = None,
    highs_map: dict | None = None,
    *,
    regime: str | None = None,
    top_n: int = _DEFAULT_TOP_N,
    require_bars: int = _REQUIRE_BARS,
) -> dict:
    """The sector-first screen rows (design §5.1): multifactor rank (reused)
    + grade band + regime cap + RRG quadrant, plus the pullback-divergence
    leader flags and dispersion-trend context. None-safe."""
    ranking = rank_sectors_multifactor(closes_map or {}, bench_closes=bench_closes)
    rows = ranking.get("ranked") or []
    if not rows:
        return {"rows": [], "leaders": [], "divergence": None, "dispersion": None,
                "regime": None, "top_n": top_n}
    if regime is None:
        regime = classify_regime(bench_closes or [])
    for r in rows:
        r["grade"] = grade_for(r.get("score"))
        r["grade_capped"] = cap_grade(r["grade"], regime)
    div = pullback_divergence(closes_map, bench_closes or [], highs_map=highs_map)
    disp = dispersion_trend(dispersion_series(closes_map))
    return {"rows": rows, "leaders": div["leaders"], "divergence": div,
            "dispersion": disp, "regime": regime, "top_n": top_n}


def constituent_screens(
    closes_map: dict,
    constituent_closes: dict,
    *,
    top_n: int = 3,
) -> dict:
    """Breadth + EW/CW + Setup A/B for the top sectors' constituents.

    ``constituent_closes``: {parent_etf: {ticker: closes}} fetched lazily by
    the tool behind ``enable_sector_breadth``. Each parent in
    ``SECTOR_CONSTITUENTS`` gets breadth (%-above-50d SMA via
    ``constituent_breadth``), the EW/CW leadership ratio and per-name
    Setup-A/B states (Setup-A needs the name's highs/volumes, passed in
    ``constituent_closes`` as {ticker: {"closes":..., "highs":..., "volumes":...}}
    when present). Anything unresolvable renders n/a, never fabricated.
    """
    out: dict = {}
    vetted = {e: cc for e, cc in (constituent_closes or {}).items() if cc}
    for etf, members in vetted.items():
        parent_closes = (closes_map or {}).get(etf) or []
        closes_only = {t: (m.get("closes") if isinstance(m, dict) else m) or []
                       for t, m in members.items()}
        highs_by = {t: (m.get("highs") if isinstance(m, dict) else []) or []
                    for t, m in members.items()}
        vols_by = {t: (m.get("volumes") if isinstance(m, dict) else []) or []
                   for t, m in members.items()}
        opens_by = {t: (m.get("opens") if isinstance(m, dict) else []) or []
                    for t, m in members.items()}
        breadth = constituent_breadth(closes_only, window=50)
        ratio = leadership_ratio(closes_only, parent_closes)
        rows = []
        for t in members:
            a = setup_a(closes_only[t], highs_by.get(t), vols_by.get(t)) if closes_only.get(t) else {"state": "none", "dist": None, "reasons": ["no series"]}
            b = setup_b(closes_only[t], opens_by.get(t)) if closes_only.get(t) else {"state": "none", "dist": None, "reasons": ["no series"]}
            rows.append({"ticker": t, "setup_a": a, "setup_b": b})
        out[etf] = {
            "breadth": breadth,
            "leadership": ratio,
            "setups": rows,
            "members": len(members),
        }
    return out


# In-process sector-lookup cache (EODHD member tagging is the expensive
# part: FMP profile call or a guarded yfinance fallback). Survives the run so
# repeat screens never re-classify the same ticker.
_SECTOR_LOOKUP_CACHE: dict[str, str | None] = {}


def constituent_universe(
    symbols: list,
    sector_of,
    *,
    per_sector_cap: int = 10,
    budget: int = 40,
) -> dict:
    """Bucket Common-Stock symbols into the 11 SPDR groups via ``sector_of``.

    ``sector_of(ticker) -> GICS sector name`` (network; the caller's free-tier
    budget drives ``budget`` - the repo's FMP key is 250 req/day and yfinance
    is throttled, so we classify only up to ``budget`` symbols, stop early
    once every sector reaches ``per_sector_cap``, and cache each lookup.
    Returns ``{spdr_etf: [tickers, ...], 'stats': {...}}`` - sectors with zero
    classified members are absent (the caller renders n/a, never fabricated).
    """
    from .sector_rank import sector_group_of

    buckets: dict[str, list] = {}
    looked_up = 0
    dead_streak = 0
    for item in symbols or []:
        if not isinstance(item, dict):
            continue
        code = str(item.get("Code") or "").strip().upper()
        if item.get("Type") not in (None, "Common Stock"):
            continue
        if not code:
            continue
        etf = _SECTOR_LOOKUP_CACHE.get(code)
        if etf is None and code not in _SECTOR_LOOKUP_CACHE:
            if looked_up >= budget:
                break
            _SECTOR_LOOKUP_CACHE[code] = sector_group_of(sector_of(code))
            looked_up += 1
        etf = _SECTOR_LOOKUP_CACHE.get(code)
        if etf is None:
            # every source failing (FMP quota + yfinance throttled) means
            # further lookups are wasted: bail before burning the budget
            dead_streak += 1
            if dead_streak >= max(6, budget // 3):
                buckets["stats"] = {
                    "n_looked_up": looked_up,
                    "n_bucketed": sum(len(v) for v in buckets.values()),
                    "cached": len(_SECTOR_LOOKUP_CACHE),
                    "dead": True,
                }
                return buckets
            continue
        dead_streak = 0
        members = buckets.setdefault(etf, [])
        if len(members) >= per_sector_cap:
            continue
        members.append(code)
    buckets["stats"] = {
        "n_looked_up": looked_up,
        "n_bucketed": sum(len(v) for v in buckets.values()),
        "cached": len(_SECTOR_LOOKUP_CACHE),
        "dead": False,
    }
    return buckets


def breadth_with_gate(breadth: dict | None, min_n: int = 20) -> dict:
    """Apply the denominator-integrity gate to a breadth read.

    n < min_n -> the breadth % is NOT a real breadth measure (a 3-ticker
    sample cannot represent a sector); render it n/a with the reason instead
    of presenting a noisy percentage. n=0 (no series) stays n/a.
    """
    if not breadth:
        return {"pct": None, "n": 0, "above": 0, "small_sample": True, "min_n": min_n}
    n = breadth.get("n", 0)
    if n and n < min_n:
        return {**breadth, "pct": None, "small_sample": True, "min_n": min_n,
                "reason": f"sample {n} < {min_n} (not a breadth read)"}
    return {**breadth, "small_sample": False, "min_n": min_n}


def leadership_ratio_ewcw(cw_closes: list, ew_closes: list, *, sma_w: int = 50) -> dict:
    """EW/CW leadership ratio vs its OWN moving average (the standard fix).

    ``ratio`` = (1+ew_total_ret)/(1+cw_total_ret) over the shared window —
    unitless and immune to nominal share-price levels (return ratios, so
    RSPT/XLK price levels cancel). Broadening = the ratio is ABOVE its own
    ``sma_w`` average (relative spread expanding); narrowing = below.
    None-safe: any missing/insufficient series returns all-None fields.
    """
    n = min(len(cw_closes or []), len(ew_closes or []))
    if n < 2:
        return {"ratio": None, "ratio_sma": None, "spread_pct": None, "label": None}
    c = cw_closes[-n:]
    e = ew_closes[-n:]
    cw_ret = c[-1] / c[0] - 1.0
    ew_ret = e[-1] / e[0] - 1.0
    if cw_ret <= -1 or ew_ret <= -1 or c[0] <= 0 or e[0] <= 0:
        return {"ratio": None, "ratio_sma": None, "spread_pct": None, "label": None}
    ratio = (1.0 + ew_ret) / (1.0 + cw_ret)
    # per-bar ratio series over the shared window (for the own-SMA baseline)
    rser = []
    for i in range(1, n):
        cw_i = c[i] / c[i - 1] - 1.0
        ew_i = e[i] / e[i - 1] - 1.0
        if cw_i > -1 and ew_i > -1:
            rser.append((1.0 + ew_i) / (1.0 + cw_i))
    if len(rser) < 2:
        return {"ratio": round(ratio, 4), "ratio_sma": None,
                "spread_pct": None, "label": None}
    k = min(sma_w, len(rser))
    sma = sum(rser[-k:]) / k
    spread = (ratio / sma - 1.0) * 100 if sma else 0.0
    return {"ratio": round(ratio, 4), "ratio_sma": round(sma, 4),
            "spread_pct": round(spread, 2),
            "label": "broadening" if ratio > sma else ("narrowing" if ratio < sma else "flat")}


def backtest_rotation(
    closes_map: dict,
    bench_closes: list,
    *,
    hold_bars: int = 21,
    top_n: int = 3,
    cost_bps: float = 5.0,
    min_bars: int = _REQUIRE_BARS,
) -> dict:
    """Monthly-rebalance top-3 rotation vs equal-weight basket vs benchmark.

    No lookahead: each rebalance uses only history up to that bar;
    ``cost_bps`` is charged per rebalance on the gross weight rotated. Returns
    aligned simple-return lists (strategy / equal-weight basket / benchmark)
    + the total turnover in units. This is the after-cost trust gate (P4) —
    downstream evaluate.py stats decide whether any claim is safe to make.
    """
    etfs = sorted((closes_map or {}).keys())
    if not etfs or not bench_closes:
        return {"strategy": [], "equal": [], "bench": [], "turns": 0.0}
    n = min(len(bench_closes), min(len(closes_map[e]) for e in etfs))
    if n < min_bars + 1:
        return {"strategy": [], "equal": [], "bench": [], "turns": 0.0}
    strat: list[float] = []
    equal: list[float] = []
    bench: list[float] = []
    positions: dict[str, float] = {}
    turns = 0.0
    for i in range(min_bars, n - 1):
        elapsed = i - min_bars
        if elapsed % hold_bars == 0:
            hist = {e: (closes_map[e])[: i + 1] for e in etfs if len(closes_map[e]) >= i + 1}
            bench_hist = bench_closes[: i + 1]
            rank = rank_sectors_multifactor(
                {e: c for e, c in hist.items() if len(c) >= min_bars},
                bench_closes=bench_hist,
            )
            top3 = (rank.get("top3_3m") or [])[:top_n]
            new_pos = {e: (1.0 / len(top3) if top3 and e in top3 else 0.0) for e in etfs}
            turns += sum(abs(new_pos.get(e, 0.0) - positions.get(e, 0.0)) for e in etfs)
            positions = new_pos

        def ret_of(e: str, idx: int = i) -> float:
            c = closes_map[e]
            return c[idx + 1] / c[idx] - 1.0 if c[idx] else 0.0

        sr = sum(positions.get(e, 0.0) * ret_of(e) for e in etfs)
        er = _mean([ret_of(e) for e in etfs])
        br = bench_closes[i + 1] / bench_closes[i] - 1.0 if bench_closes[i] else 0.0
        # charge the rotation cost spread over the holding period
        sr -= (turns * cost_bps * 1e-4) / hold_bars
        strat.append(sr)
        equal.append(er if er is not None else 0.0)
        bench.append(br)
    return {"strategy": strat, "equal": equal, "bench": bench, "turns": round(turns, 4)}


__all__ = [
    "_sma_last",
    "_ema",
    "classify_regime",
    "grade_for",
    "cap_grade",
    "dispersion_series",
    "dispersion_trend",
    "pullback_divergence",
    "setup_a",
    "setup_b",
    "stock_screen",
    "_architecture",
    "_rel_outperformance",
    "_no_chase",
    "sector_screen",
    "constituent_screens",
    "constituent_universe",
    "breadth_with_gate",
    "leadership_ratio_ewcw",
    "backtest_rotation",
]

