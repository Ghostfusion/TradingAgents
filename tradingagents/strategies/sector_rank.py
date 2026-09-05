"""Phase 2 - sector & industry group confirmation (top 3 of 11 SPDR groups).

The swing framework requires the candidate's sector to be a top performer over
a rolling 1-month and 3-month window (e.g. the top 3 of the 11 SPDR sector
ETFs). This module ranks the SPDR groups purely from their daily close series
- the screener feeds the closes from the vendor chain and reads the flags back.
"""

from __future__ import annotations

# The 11 SPDR sector ETFs (XLY=XLC renamed in 1998; kept the current ticker).
SPDR_SECTORS = {
    "XLE": "Energy",
    "XLF": "Financials",
    "XLK": "Technology",
    "XLV": "Health Care",
    "XLI": "Industrials",
    "XLY": "Consumer Disc.",
    "XLP": "Consumer Staples",
    "XLB": "Materials",
    "XLRE": "Real Estate",
    "XLU": "Utilities",
    "XLC": "Communications",
}


def _momentum(closes: list, window: int) -> float | None:
    """Return over the trailing ``window`` bars (close vs window bars ago)."""
    if not closes or len(closes) <= window:
        return None
    base = closes[-window - 1]
    if base is None or base <= 0:
        return None
    return closes[-1] / base - 1.0


def rank_sectors(closes_map: dict, window_1m: int = 21, window_3m: int = 63) -> dict:
    """Rank the SPDR groups by 3-month momentum (primary) + 1-month standing.

    ``closes_map``: {SPDR ticker: daily closes}. Sectors with insufficient
    history sort last and are never ranked top-3. Returns ``None`` when no
    usable series at all.
    """
    rows = []
    for etf, closes in (closes_map or {}).items():
        r1 = _momentum(closes, window_1m)
        r3 = _momentum(closes, window_3m)
        rows.append(
            {
                "etf": etf,
                "name": SPDR_SECTORS.get(etf, etf),
                "ret_1m": round(r1, 4) if r1 is not None else None,
                "ret_3m": round(r3, 4) if r3 is not None else None,
                "rank": None,
            }
        )
    ranked = sorted(rows, key=lambda r: (r["ret_3m"] is None, -(r["ret_3m"] or 0.0)))
    for i, r in enumerate(ranked, 1):
        r["rank"] = i if r["ret_3m"] is not None else None
    by_1m = sorted(rows, key=lambda r: (r["ret_1m"] is None, -(r["ret_1m"] or 0.0)))
    valid = [r for r in ranked if r["ret_3m"] is not None]
    if not valid:
        return {"ranked": ranked, "top3_3m": [], "top3_1m": []}
    top3_3m = [r["etf"] for r in ranked[:3] if r["rank"] is not None]
    top3_1m = [r["etf"] for r in by_1m[:3] if r["ret_1m"] is not None]
    return {"ranked": ranked, "top3_3m": top3_3m, "top3_1m": top3_1m}


def _canonical_sector(sector: str) -> str:
    """Map a GICS/yfinance sector string to the SPDR short label (lowercase)."""
    key = sector.strip().lower()
    return _GICS_TO_SPDR.get(key, key)


# GICS naming vs the SPDR short labels (FMP/av profile and yfinance report
# GICS names; the SPDR group names differ in spelling, e.g. "Financial
# Services" vs "Financials", "Information Technology" vs "Technology").
_GICS_TO_SPDR = {
    "information technology": "technology",
    "communication services": "communications",
    "consumer discretionary": "consumer disc.",
    "financial services": "financials",
    "financial": "financials",
    "healthcare": "health care",
    "consumer staples": "consumer staples",
    "real estate": "real estate",
    "utilities": "utilities",
    "energy": "energy",
    "materials": "materials",
    "industrials": "industrials",
}


def sector_standing(sector: str | None, ranking: dict | None) -> dict:
    """Where a candidate's sector sits in the ranking.

    Verdicts: ``top3`` (in the 3-month top-3), ``tracking`` (ranked but not
    top-3), ``unknown`` (sector or ranking unavailable).
    """
    if not sector or not ranking:
        return {
            "sector": sector,
            "rank": None,
            "top3_3m": None,
            "top3_1m": None,
            "verdict": "unknown",
        }
    sector = sector.strip()
    canon = _canonical_sector(sector)
    for r in ranking.get("ranked", []):
        name = str(r.get("name", "")).lower()
        if canon == name or (canon and (canon in name or name in canon)):
            top3 = r["etf"] in ranking.get("top3_3m", [])
            return {
                "sector": r["name"],
                "rank": r["rank"],
                "etf": r["etf"],
                "top3_3m": top3,
                "top3_1m": r["etf"] in ranking.get("top3_1m", []),
                "verdict": "top3" if top3 else "tracking",
            }
    return {"sector": sector, "rank": None, "top3_3m": None, "top3_1m": None, "verdict": "unknown"}


# ---------------------------------------------------------------------------
# Sector rotation P1-P3 (strategies/formulas/sector_rotation.md):
# multi-factor rank, two-level industry rank, constituent breadth + EW/CW.
# All advisory; every factor is None-safe and every score is a cross-sectional
# percentile (0-100). The legacy single-factor path stays byte-identical.
# ---------------------------------------------------------------------------

# Log-return period windows used by the P1 momentum composite (weights mirror
# the reference doc: 21d 5% / 63d 30% / 126d 30% / 252d 25% / accel 10%).
_MOMENTUM_WINDOWS = (21, 63, 126, 252)
_MOMENTUM_WEIGHTS = (0.05, 0.30, 0.30, 0.25)
_MOMENTUM_ACCEL_W = 0.10

# P1 factor weights over the four factors computed at this phase (normalized
# from the doc's 25/15/15/15, summing to 1.0): momentum .37, RS .21, trend
# .21, risk .21.
FACTOR_WEIGHTS = {"momentum": 0.37, "rs": 0.21, "trend": 0.21, "risk": 0.21}


def _sma_last(closes: list, window: int) -> float | None:
    """Last value of a simple moving average (None when not enough bars)."""
    if not closes or len(closes) < window:
        return None
    vals = closes[-window:]
    if any(v is None or v <= 0 for v in vals):
        return None
    return sum(vals) / window


def _ma_alignment(closes: list) -> float | None:
    """Price vs SMA alignment score in [0, 1] (doc: five +1 conditions)."""
    try:
        p = closes[-1]
        s20, s50, s100, s200 = (_sma_last(closes, w) for w in (20, 50, 100, 200))
        if any(v is None for v in (s20, s50, s100, s200)) or p is None:
            return None
        conds = (p > s20, s20 > s50, s50 > s100, s100 > s200, p > s200)
        return sum(1 for c in conds if c) / 5.0
    except Exception:  # noqa: BLE001 - advisory
        return None


def _daily_returns(closes: list) -> tuple:
    """Daily simple returns from closes; (returns, mean, stdev, n)."""
    try:
        rs = [closes[i] / closes[i - 1] - 1.0 for i in range(1, len(closes))
              if closes[i] is not None and closes[i - 1] is not None and closes[i - 1] > 0]
        if len(rs) < 2:
            return [], 0.0, 0.0, 0
        m = sum(rs) / len(rs)
        v = sum((r - m) ** 2 for r in rs) / (len(rs) - 1)
        return rs, m, v ** 0.5, len(rs)
    except Exception:  # noqa: BLE001 - advisory
        return [], 0.0, 0.0, 0


def _sharpe_window(closes: list, window: int, risk_free: float = 0.0) -> float | None:
    """Annualized Sharpe over the trailing ``window`` bars (None-safe)."""
    if not closes or len(closes) < window + 1:
        return None
    rs, m, sd, _n = _daily_returns(closes[-window - 1:])
    if sd <= 0:
        return None
    return (m - risk_free / 252.0) / sd * (252.0 ** 0.5)


def _max_drawdown(closes: list, window: int) -> float | None:
    """Trailing-window maximum drawdown magnitude (0..1) or None."""
    if not closes or len(closes) < window:
        return None
    peak = -1.0
    worst = 0.0
    for c in closes[-window:]:
        if c is None or c <= 0:
            continue
        if c > peak:
            peak = c
        if peak > 0:
            worst = min(worst, c / peak - 1.0)
    return -worst


def _acceleration(closes: list, short_w: int = 63, long_w: int = 126) -> float | None:
    """Momentum acceleration ``R_short - 0.5*R_long`` (None-safe)."""
    if not closes or len(closes) <= long_w:
        return None
    base_s = closes[-short_w - 1]
    base_l = closes[-long_w - 1]
    if base_s is None or base_s <= 0 or base_l is None or base_l <= 0:
        return None
    r_s = closes[-1] / base_s - 1.0
    r_l = closes[-1] / base_l - 1.0
    return r_s - 0.5 * r_l


def _trend_raw(closes: list) -> float | None:
    """Trend factor raw: blend of P/SMA50, P/SMA200 and MA alignment."""
    try:
        p = closes[-1]
        s50, s200 = _sma_last(closes, 50), _sma_last(closes, 200)
        align = _ma_alignment(closes)
        parts = []
        if s50 and s50 > 0 and p is not None:
            parts.append(p / s50 - 1.0)
        if s200 and s200 > 0 and p is not None:
            parts.append(p / s200 - 1.0)
        if align is not None:
            parts.append(align)
        if not parts:
            return None
        return sum(parts) / len(parts)
    except Exception:  # noqa: BLE001 - advisory
        return None


def _rs_ratio_return(closes: list, bench_closes: list, window: int) -> float | None:
    """Relative-strength ratio return: (ETF/benchmark) window change."""
    if not closes or not bench_closes or window < 1:
        return None
    n = min(len(closes), len(bench_closes))
    if n <= window:
        return None
    c, b = closes[-n:], bench_closes[-n:]
    r_now = c[-1] / b[-1] if b[-1] else None
    r_base = c[-window - 1] / b[-window - 1] if b[-window - 1] else None
    if not r_now or not r_base or r_now <= 0 or r_base <= 0:
        return None
    return r_now / r_base - 1.0


def _pct_rank(values: dict, good_high: bool = True) -> dict:
    """Cross-sectional percentile (0-100) per ETF for one factor.

    Ties share the mean rank (true percentile semantics); ``good_high`` =
    a higher raw ranks better (False inverts, e.g. drawdown). None raws stay
    None; N==1 -> 50.0.
    """
    valid = sorted(
        ((etf, v) for etf, v in values.items() if v is not None),
        key=lambda kv: kv[1],
    )
    if not valid:
        return {}
    if len(valid) == 1:
        return {valid[0][0]: 50.0}
    out = {}
    i = 0
    n = len(valid)
    while i < n:
        j = i
        while j + 1 < n and valid[j + 1][1] == valid[i][1]:
            j += 1
        mid_rank = (i + 1 + j + 1) / 2.0  # mean 1-based rank of the tie group
        pct = 100.0 * (mid_rank - 1) / (n - 1)
        for k in range(i, j + 1):
            out[valid[k][0]] = pct
        i = j + 1
    if not good_high:  # invert so small raws rank high (e.g. |drawdown|)
        for etf in out:
            out[etf] = 100.0 - out[etf]
    return out


def rrg_quadrant(rs_level: float | None, rs_momentum: float | None) -> str | None:
    """RRG quadrant from the RS percentile axes (Action 1; RRG reference).

    ``rs_level`` = percentile of the RS-Ratio (ranking), ``rs_momentum`` =
    percentile of RS-Ratio acceleration (timing). Intersection of the two
    median splits:
      Leading    level >= 50 and momentum >= 50  - strongest hold candidates
      Weakening  level >= 50 and momentum <  50  - exit/reduction warning
      Improving  level <  50 and momentum >= 50  - early-entry watchlist
      Lagging    level <  50 and momentum <  50  - avoid/underweight
    Returns None when either axis is missing (never fabricates a quadrant).
    The two axes stay separate: momentum turns before level, so Improving/
    Weakening precede Leading/Lagging in the clockwise rotation.
    """
    if rs_level is None or rs_momentum is None:
        return None
    if rs_level >= 50.0:
        return "Leading" if rs_momentum >= 50.0 else "Weakening"
    return "Improving" if rs_momentum >= 50.0 else "Lagging"


def rank_sectors_multifactor(
    closes_map: dict,
    bench_closes: list | None = None,
    *,
    min_bars: int = 65,
) -> dict:
    """Multi-factor SPDR sector rank (sector_rotation P1).

    Factors (each cross-sectional percentile 0-100): ``momentum`` composite
    (21/63/126/252d + acceleration), ``rs`` vs the benchmark (SPY) ratio
    returns, ``trend`` (P/SMA50 + P/SMA200 + MA alignment), ``risk`` (Sharpe
    126d blended with 1 - |MDD| 126d percentile). ``score`` = weighted sum
    (FACTOR_WEIGHTS, renormalized over the factors that actually computed).

    Result shape mirrors ``rank_sectors`` (ranked / top3_3m / top3_1m) so
    ``sector_standing`` consumes it unchanged; each row carries the raw
    factors + percentile subfactors + ``score`` + ``rank`` + ``accel``.
    """
    rows = []
    for etf, closes in (closes_map or {}).items():
        row = {"etf": etf, "name": SPDR_SECTORS.get(etf, etf), "rank": None}
        if not closes or len(closes) < min_bars:
            row.update({"ret_1m": None, "ret_3m": None, "accel": None, "sma50": None,
                        "sharpe_126": None, "mdd_126": None, "trend_raw": None,
                        "momentum_raw": None, "rs_raw": None, "risk_raw": None,
                        "rs_momentum": None, "quadrant": None, "score": None})
            rows.append(row)
            continue
        row["ret_1m"] = round(_momentum(closes, 21), 4) if _momentum(closes, 21) is not None else None
        row["ret_3m"] = round(_momentum(closes, 63), 4) if _momentum(closes, 63) is not None else None
        row["accel"] = round(_acceleration(closes), 4) if _acceleration(closes) is not None else None
        row["sma50"] = round(_sma_last(closes, 50) / closes[-1] - 1.0, 4) if _sma_last(closes, 50) else None
        row["sharpe_126"] = round(_sharpe_window(closes, 126), 4) if _sharpe_window(closes, 126) is not None else None
        row["mdd_126"] = round(_max_drawdown(closes, 126), 4) if _max_drawdown(closes, 126) is not None else None
        row["momentum_raw"] = None
        row["rs_raw"] = None
        row["trend_raw"] = _trend_raw(closes)
        row["risk_raw"] = None
        rows.append(row)

    row_by = {r["etf"]: r for r in rows}
    # momentum raw: weighted sum of the window returns (None unless ALL
    # windows resolve), then cross-sectional percentile.
    m_raw: dict[str, float] = {}
    for etf, closes in (closes_map or {}).items():
        if etf not in row_by or row_by[etf]["ret_3m"] is None:
            continue
        rets = []
        ok = True
        for _i, w in enumerate(_MOMENTUM_WINDOWS):
            v = _momentum(closes, w)
            if v is None:
                ok = False
                break
            rets.append(v)
        if ok:
            m_raw[etf] = sum(wt * v for wt, v in zip(_MOMENTUM_WEIGHTS, rets, strict=True))
    m_pct = _pct_rank(m_raw)

    # momentum accel percentile blended over the composite.
    accel_raw = {etf: r["accel"] for etf, r in row_by.items() if r["accel"] is not None}
    accel_pct = _pct_rank(accel_raw)
    for etf, r in row_by.items():
        base = m_pct.get(etf)
        acc = accel_pct.get(etf)
        if base is None and acc is None:
            r["momentum"] = None
            continue
        r["momentum"] = round(
            (base if base is not None else 50.0) * (1 - _MOMENTUM_ACCEL_W)
            + (acc if acc is not None else base or 50.0) * _MOMENTUM_ACCEL_W,
            2,
        )

    # rs vs benchmark
    rs_raw: dict[str, float] = {}
    if bench_closes:
        for etf, r in row_by.items():
            if r["ret_3m"] is None:
                continue
            v = _rs_ratio_return(closes_map[etf], bench_closes, 63)
            if v is not None:
                rs_raw[etf] = v
    rs_pct = _pct_rank(rs_raw)
    for etf, r in row_by.items():
        r["rs"] = rs_pct.get(etf)

    # rs momentum: acceleration of the RS ratio (63d vs 126d), percentile-
    # ranked across the universe - the RRG timing axis, kept SEPARATE from the
    # rs level (RRG: RS-Ratio = ranking signal, RS-Momentum = timing signal).
    rsm_raw: dict[str, float] = {}
    if bench_closes:
        for etf, r in row_by.items():
            if r["ret_3m"] is None:
                continue
            try:
                rs63 = _rs_ratio_return(closes_map[etf], bench_closes, 63)
                rs126 = _rs_ratio_return(closes_map[etf], bench_closes, 126)
                if rs63 is not None and rs126 is not None:
                    rsm_raw[etf] = rs63 - 0.5 * rs126
            except Exception:  # noqa: BLE001 - advisory
                continue
    rsm_pct = _pct_rank(rsm_raw)
    for etf, r in row_by.items():
        r["rs_momentum"] = rsm_pct.get(etf)
        r["quadrant"] = rrg_quadrant(r["rs"], r["rs_momentum"])

    # trend
    trend_raw = {etf: r["trend_raw"] for etf, r in row_by.items() if r["trend_raw"] is not None}
    trend_pct = _pct_rank(trend_raw)
    for etf, r in row_by.items():
        r["trend"] = trend_pct.get(etf)

    # risk: sharpe + (1 - |mdd| pct)
    sharpe_raw = {etf: r["sharpe_126"] for etf, r in row_by.items() if r["sharpe_126"] is not None}
    mdd_raw = {etf: r["mdd_126"] for etf, r in row_by.items() if r["mdd_126"] is not None}
    sharpe_pct = _pct_rank(sharpe_raw)
    mdd_pct = _pct_rank(mdd_raw, good_high=False)
    for etf, r in row_by.items():
        s = sharpe_pct.get(etf)
        d = mdd_pct.get(etf)
        r["risk"] = round(0.6 * (s if s is not None else 0.0) + 0.4 * (d if d is not None else 0.0), 2) if (s is not None or d is not None) else None

    # weighted score over available factors
    for _etf, r in row_by.items():
        avail = [(k, w) for k, w in FACTOR_WEIGHTS.items() if r.get(k) is not None]
        if not avail:
            continue
        tot_w = sum(w for _, w in avail)
        r["score"] = round(sum(r[k] * w for k, w in avail) / tot_w, 2) if tot_w else None
        # percentile rank for *_pct already 0-100; score is an average of them.
    ranked = sorted(rows, key=lambda r: (r.get("score") is None, -(r.get("score") or 0.0)))
    for i, r in enumerate(ranked, 1):
        r["rank"] = i if r.get("score") is not None else None
    by_1m = sorted(rows, key=lambda r: (r["ret_1m"] is None, -(r["ret_1m"] or 0.0)))
    return {
        "ranked": ranked,
        "top3_3m": [r["etf"] for r in ranked[:3] if r["rank"] is not None],
        "top3_1m": [r["etf"] for r in by_1m[:3] if r["ret_1m"] is not None],
        "multifactor": True,
    }


# Industry layer (P2): Level-2 industry ETFs ranked only INSIDE their parent
# sector, so XLK (sector) and SOXX (industry) are never in the same pool.
INDUSTRY_ETFS: dict[str, tuple] = {
    "SOXX": ("XLK", "Semiconductors"),
    "IGV": ("XLK", "Software"),
    "HACK": ("XLK", "Cybersecurity"),
    "CLOU": ("XLK", "Cloud"),
    "SMH": ("XLK", "Semiconductors"),
    "XBI": ("XLV", "Biotech"),
    "IBB": ("XLV", "Biotech"),
    "KRE": ("XLF", "Banks"),
    "XHB": ("XLY", "Homebuilders"),
    "XAR": ("XLI", "Aerospace & Defense"),
    "XOP": ("XLE", "Oil & Gas E&P"),
    "XRT": ("XLY", "Retail"),
}


def rank_industry_group(
    closes_map: dict,
    parent_etf: str,
    bench_closes: list | None = None,
    *,
    min_bars: int = 65,
) -> dict:
    """Rank the industry ETFs whose parent is ``parent_etf`` (P2).

    Only ETFs listed in ``INDUSTRY_ETFS`` with that parent enter the pool;
    single-factor 3m momentum by default, multi-factor when ``bench_closes``
    is provided (reuses the multifactor machinery). Returns the same shape as
    ``rank_sectors_multifactor`` (ranked / top3_3m / empty when none).
    """
    sub = {etf: closes for etf, closes in (closes_map or {}).items()
           if etf in INDUSTRY_ETFS and INDUSTRY_ETFS[etf][0] == parent_etf}
    if not sub:
        return {"ranked": [], "top3_3m": [], "top3_1m": [], "industry_of": parent_etf}
    if bench_closes:
        ranking = rank_sectors_multifactor(sub, bench_closes=bench_closes, min_bars=min_bars)
        for r in ranking["ranked"]:
            if r["etf"] in INDUSTRY_ETFS:
                r["name"] = INDUSTRY_ETFS[r["etf"]][1]
    else:
        rows = []
        for etf, closes in sub.items():
            r3 = _momentum(closes, 63)
            rows.append({"etf": etf, "name": INDUSTRY_ETFS[etf][1], "ret_3m": round(r3, 4) if r3 is not None else None, "rank": None, "score": None})
        ranked = sorted(rows, key=lambda r: (r["ret_3m"] is None, -(r["ret_3m"] or 0.0)))
        for i, r in enumerate(ranked, 1):
            r["rank"] = i if r["ret_3m"] is not None else None
        ranking = {"ranked": ranked, "top3_3m": [r["etf"] for r in ranked[:3] if r["rank"] is not None], "top3_1m": [], "industry_of": parent_etf}
    ranking["industry_of"] = parent_etf
    return ranking


# P3 constituent breadth + equal-weight leadership (advisory; a curated core
# subset — full breadth would need the complete constituent lists, which the
# doc marks fetch-heavy; anything missing renders n/a, never fabricated).
SECTOR_CONSTITUENTS: dict[str, list] = {
    "SOXX": ["NVDA", "AMD", "AVGO", "MU", "TSM", "AMAT", "LRCX", "KLAC", "MRVL", "QCOM"],
    "XBI": ["MRNA", "REGN", "VRTX", "AMGN", "GILD", "ILMN", "ALNY", "BIIB", "MGNX", "NTLA"],
}


def constituent_breadth(closes_map: dict, window: int = 50) -> dict:
    """Fraction of constituents above their SMA(window) (P3).

    ``closes_map``: {constituent: closes}. Returns ``{"pct": .., "n": ..,
    "above": .., "window": window}`` or ``{"pct": None, "n": 0}`` when no
    usable series.
    """
    above, n = 0, 0
    for closes in (closes_map or {}).values():
        sma = _sma_last(closes, window)
        if sma is None or not closes:
            continue
        n += 1
        if closes[-1] > sma:
            above += 1
    if not n:
        return {"pct": None, "n": 0, "above": 0, "window": window}
    return {"pct": round(100.0 * above / n, 1), "n": n, "above": above, "window": window}


def leadership_ratio(constituents_map: dict, etf_closes: list) -> float | None:
    """Equal-weight vs cap-weight leadership ratio (P3).

    EW total return = mean of the constituents' total returns over the shared
    window; CW = the ETF's own (cap-weighted) total return. Ratio > 1 means
    the equal-weight basket led (broad participation); < 1 means the
    cap-weighted ETF led (narrow/mega-cap concentration, e.g. SOXX).
    """
    try:
        es = [c for c in constituents_map.values() if c and len(c) > 1]
        if not es or not etf_closes or len(etf_closes) < 2:
            return None
        n = min([len(c) for c in es] + [len(etf_closes)])
        if n < 2:
            return None
        rets = []
        for c in es:
            cc = c[-n:]
            base, last = cc[0], cc[-1]
            if base and base > 0 and last is not None:
                rets.append(last / base - 1.0)
        if not rets:
            return None
        ec = etf_closes[-n:]
        if not ec[0] or ec[0] <= 0 or ec[-1] is None:
            return None
        ew_ret = sum(rets) / len(rets)
        cw_ret = ec[-1] / ec[0] - 1.0
        if cw_ret <= -1:
            return None
        return round((1.0 + ew_ret) / (1.0 + cw_ret), 3)
    except Exception:  # noqa: BLE001 - advisory
        return None


__all__ = [
    "SPDR_SECTORS",
    "rank_sectors",
    "sector_standing",
    "rank_sectors_multifactor",
    "rrg_quadrant",
    "INDUSTRY_ETFS",
    "rank_industry_group",
    "SECTOR_CONSTITUENTS",
    "constituent_breadth",
    "leadership_ratio",
    "FACTOR_WEIGHTS",
]
