"""SPDR sector-ranking module tests - pure/offline."""

import pytest

from tradingagents.strategies.sector_rank import (
    FACTOR_WEIGHTS,
    INDUSTRY_ETFS,
    SECTOR_CONSTITUENTS,
    SPDR_SECTORS,
    constituent_breadth,
    leadership_ratio,
    rank_industry_group,
    rank_sectors,
    rank_sectors_multifactor,
    rrg_quadrant,
    sector_standing,
)

pytestmark = pytest.mark.timeout(60)


def _up(start: float, step: float, n: int = 80) -> list:
    return [start + step * i for i in range(n)]


def test_spdr_has_11_sectors():
    assert len(SPDR_SECTORS) == 11
    assert SPDR_SECTORS["XLK"] == "Technology"
    assert SPDR_SECTORS["XLF"] == "Financials"


def test_rank_sectors_orders_by_3m():
    closes_map = {
        "XLK": _up(100.0, 0.8),  # strongest
        "XLF": _up(100.0, 0.4),
        "XLE": _up(100.0, 0.1),  # weakest
    }
    r = rank_sectors(closes_map)
    assert [x["etf"] for x in r["ranked"]] == ["XLK", "XLF", "XLE"]
    assert r["top3_3m"] == ["XLK", "XLF", "XLE"]
    assert r["ranked"][0]["rank"] == 1
    assert r["ranked"][2]["rank"] == 3


def test_rank_insufficient_history_not_ranked():
    closes_map = {
        "XLK": _up(100.0, 0.8),
        "XLF": [100.0] * 10,  # too short for a 63-day window
    }
    r = rank_sectors(closes_map)
    xlf = [x for x in r["ranked"] if x["etf"] == "XLF"][0]
    assert xlf["rank"] is None
    assert "XLF" not in r["top3_3m"]


def test_rank_no_data_returns_empty():
    r = rank_sectors({})
    assert r["ranked"] == []
    assert r["top3_3m"] == []


def test_sector_standing_top3_and_tracking():
    closes_map = {
        "XLK": _up(100.0, 0.8),
        "XLF": _up(100.0, 0.4),
        "XLV": _up(100.0, 0.2),
        "XLE": _up(100.0, 0.1),  # 4th - outside the top-3
    }
    ranking = rank_sectors(closes_map)
    top = sector_standing("Technology", ranking)
    assert top["verdict"] == "top3"
    assert top["rank"] == 1
    assert top["top3_3m"] is True
    tail = sector_standing("Energy", ranking)
    assert tail["verdict"] == "tracking"
    assert tail["rank"] == 4
    assert tail["top3_3m"] is False


def test_sector_standing_fuzzy_match():
    closes_map = {"XLK": _up(100.0, 0.8)}
    ranking = rank_sectors(closes_map)
    # "Computer and Technology" (industry sub-group) maps to the XLK group.
    s = sector_standing("Computer and Technology", ranking)
    assert s["sector"] == "Technology"


def test_sector_standing_gics_names_canonicalize():
    closes_map = {
        "XLK": _up(100.0, 0.8),
        "XLF": _up(100.0, 0.4),
        "XLV": _up(100.0, 0.2),
        "XLY": _up(100.0, 0.15),
        "XLE": _up(100.0, 0.1),
    }
    ranking = rank_sectors(closes_map)
    it = sector_standing("Information Technology", ranking)
    assert it["verdict"] == "top3" and it["sector"] == "Technology"
    fin = sector_standing("Financial Services", ranking)
    assert fin["verdict"] == "top3" and fin["sector"] == "Financials"
    hc = sector_standing("Health Care", ranking)
    assert hc["sector"] == "Health Care" and hc["verdict"] == "top3"
    cd = sector_standing("Consumer Discretionary", ranking)
    assert cd["sector"] == "Consumer Disc." and cd["rank"] == 4
    assert cd["verdict"] == "tracking"  # 4th - outside the top-3


def test_sector_standing_unknown():
    assert sector_standing(None, None)["verdict"] == "unknown"
    assert sector_standing("Crypto", {"ranked": []})["verdict"] == "unknown"


# ---------------------------------------------------------------------------
# Sector-rotation P1: multi-factor rank (strategies/formulas/sector_rotation.md)
# ---------------------------------------------------------------------------


def _uptrend(n: int = 260, step: float = 0.8) -> list:
    return [100.0 + step * i for i in range(n)]


def _bench(n: int = 260) -> list:
    return [100.0 + 0.2 * i for i in range(n)]


def test_multifactor_orders_by_score():
    cm = {
        "XLK": _uptrend(step=0.8),  # strong momentum
        "XLF": _uptrend(step=0.4),
        "XLE": _uptrend(step=0.1),
        "XLV": [100.0 - 0.05 * i for i in range(260)],  # falling
    }
    r = rank_sectors_multifactor(cm, bench_closes=_bench())
    ranked = [x["etf"] for x in r["ranked"]]
    assert ranked.index("XLK") < ranked.index("XLF") < ranked.index("XLE") < ranked.index("XLV")
    assert r["top3_3m"] == ["XLK", "XLF", "XLE"]
    xlk = [x for x in r["ranked"] if x["etf"] == "XLK"][0]
    assert xlk["rank"] == 1
    assert xlk["score"] > 50.0
    assert 0.0 <= xlk["momentum"] <= 100.0
    assert 0.0 <= xlk["trend"] <= 100.0
    assert 0.0 <= xlk["risk"] <= 100.0


def test_multifactor_rs_needs_benchmark():
    cm = {"XLK": _uptrend(), "XLF": _uptrend(step=0.4)}
    r_no_bench = rank_sectors_multifactor(cm, bench_closes=None)
    for row in r_no_bench["ranked"]:
        assert row.get("rs") is None  # no benchmark -> RS unavailable, never fabricated


def test_multifactor_insufficient_history_not_ranked():
    cm = {"XLK": _uptrend(), "XLF": [100.0] * 10}
    r = rank_sectors_multifactor(cm, bench_closes=_bench())
    xlf = [x for x in r["ranked"] if x["etf"] == "XLF"][0]
    assert xlf["rank"] is None and xlf["score"] is None
    assert "XLF" not in r["top3_3m"]


def test_multifactor_score_bounds_and_normalization():
    cm = {e: _uptrend(step=s) for e, s in
          [("XLK", 0.8), ("XLF", 0.4), ("XLE", 0.1), ("XLV", -0.05), ("XLY", 0.0)]}
    r = rank_sectors_multifactor(cm, bench_closes=_bench())
    for row in r["ranked"]:
        if row["score"] is not None:
            assert 0.0 <= row["score"] <= 100.0
    scores = sorted(x["score"] for x in r["ranked"] if x["score"] is not None)
    assert scores[0] < scores[-1]  # real spread (not all 50.0)


def test_multifactor_consumable_by_standing():
    cm = {"XLK": _uptrend(step=0.8), "XLF": _uptrend(step=0.4), "XLE": _uptrend(step=0.1)}
    r = rank_sectors_multifactor(cm, bench_closes=_bench())
    st = sector_standing("Technology", r)  # same shape as rank_sectors
    assert st["verdict"] == "top3" and st["rank"] == 1


def test_factor_weights_sum_to_one():
    assert abs(sum(FACTOR_WEIGHTS.values()) - 1.0) < 1e-9


# ---------------------------------------------------------------------------
# Sector-rotation P2: industry layer (ranked only inside the parent sector)
# ---------------------------------------------------------------------------


def test_industry_rank_gates_by_parent():
    ind = {
        "SOXX": _uptrend(step=0.9), "IGV": _uptrend(step=0.6), "HACK": _uptrend(step=0.3),
        "KRE": _uptrend(step=0.2),  # parent XLF - must NOT enter the XLK pool
    }
    r = rank_industry_group(ind, "XLK", _bench())
    etfs = [x["etf"] for x in r["ranked"]]
    assert etfs == ["SOXX", "IGV", "HACK"]
    assert "KRE" not in etfs
    assert r["industry_of"] == "XLK"


def test_industry_rank_names_industries():
    ind = {"SOXX": _uptrend(step=0.9), "IGV": _uptrend(step=0.6)}
    r = rank_industry_group(ind, "XLK", _bench())
    soxx = [x for x in r["ranked"] if x["etf"] == "SOXX"][0]
    assert soxx["name"] == "Semiconductors"


def test_industry_rank_empty_pool():
    ind = {"SOXX": _uptrend(step=0.9), "KRE": _uptrend(step=0.2)}
    r = rank_industry_group(ind, "XLB", _bench())  # no XLB industry ETFs given
    assert r["ranked"] == [] and r["top3_3m"] == []


def test_industry_etfs_have_parents_in_spdr():
    for _etf, (parent, name) in INDUSTRY_ETFS.items():
        assert parent in SPDR_SECTORS
        assert name


# ---------------------------------------------------------------------------
# Sector-rotation P3: constituent breadth + EW/CW leadership
# ---------------------------------------------------------------------------


def test_constituent_breadth_above_ma():
    cons = {"NVDA": _uptrend(step=1.0), "AMD": _uptrend(step=0.5), "MU": [100.0 - 0.2 * i for i in range(80)]}
    b = constituent_breadth(cons)
    assert b["pct"] == 66.7 and b["n"] == 3 and b["above"] == 2


def test_constituent_breadth_empty():
    b = constituent_breadth({})
    assert b["pct"] is None and b["n"] == 0


def test_leadership_ratio_ew_leads():
    # constituents outperform the cap-weighted ETF -> EW/CW > 1
    cons = {"NVDA": _uptrend(step=1.0), "AMD": _uptrend(step=0.9)}
    etf = _uptrend(step=0.1)
    lr = leadership_ratio(cons, etf)
    assert lr is not None and lr > 1.0


def test_leadership_ratio_cw_leads():
    # one mega-cap drags the weight -> cap-weighted beats equal-weight (< 1)
    cons = {"NVDA": _uptrend(step=1.0), "AMD": _uptrend(step=1.0)}
    etf = _uptrend(step=3.0)
    lr = leadership_ratio(cons, etf)
    assert lr is not None and lr < 1.0


def test_leadership_ratio_insufficient():
    assert leadership_ratio({}, _uptrend()) is None
    assert leadership_ratio({"NVDA": [100.0]}, []) is None


def test_constituents_core_subset_documented():
    # The curated set is small on purpose (fetch-heavy full breadth is the
    # documented P3 limit); the strings must be uppercase tickers.
    for fam, members in SECTOR_CONSTITUENTS.items():
        assert fam in INDUSTRY_ETFS
        assert members and all(m == m.upper() for m in members)


# ---------------------------------------------------------------------------
# Sector-rotation Action 1: RRG quadrant (RS-level x RS-momentum axes)
# ---------------------------------------------------------------------------


def test_rrg_quadrant_four_quadrants():
    assert rrg_quadrant(80.0, 80.0) == "Leading"
    assert rrg_quadrant(80.0, 20.0) == "Weakening"
    assert rrg_quadrant(20.0, 80.0) == "Improving"
    assert rrg_quadrant(20.0, 20.0) == "Lagging"


def test_rrg_quadrant_boundary_uses_median_split():
    assert rrg_quadrant(50.0, 50.0) == "Leading"  # >= 50 on both axes


def test_rrg_quadrant_none_never_fabricates():
    assert rrg_quadrant(None, 50.0) is None
    assert rrg_quadrant(50.0, None) is None
    assert rrg_quadrant(None, None) is None


def test_multifactor_rows_carry_quadrant():
    cm = {
        "XLK": _uptrend(step=0.8),   # strong RS
        "XLF": _uptrend(step=0.4),
        "XLE": _uptrend(step=0.1),
        "XLV": [100.0 - 0.05 * i for i in range(260)],  # weak
    }
    r = rank_sectors_multifactor(cm, bench_closes=_bench())
    xlk = [x for x in r["ranked"] if x["etf"] == "XLK"][0]
    xlv = [x for x in r["ranked"] if x["etf"] == "XLV"][0]
    assert xlk["quadrant"] in ("Leading", "Weakening")  # high RS level
    assert xlv["rs"] == 0.0  # weakest RS level -> not a leading quadrant
    assert xlv["quadrant"] in ("Lagging", "Improving")  # low level + (mom) axis
    assert all(row.get("quadrant") is not None
               for row in r["ranked"] if row.get("rs") is not None)


def test_multifactor_quadrant_none_without_benchmark():
    cm = {"XLK": _uptrend(), "XLF": _uptrend(step=0.4)}
    r = rank_sectors_multifactor(cm, bench_closes=None)
    for row in r["ranked"]:
        assert row.get("quadrant") is None  # no RS axes -> no quadrant
