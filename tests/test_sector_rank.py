"""SPDR sector-ranking module tests - pure/offline."""

from tradingagents.strategies.sector_rank import (
    SPDR_SECTORS,
    rank_sectors,
    sector_standing,
)


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


def test_sector_standing_unknown():
    assert sector_standing(None, None)["verdict"] == "unknown"
    assert sector_standing("Crypto", {"ranked": []})["verdict"] == "unknown"
