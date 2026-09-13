"""S1 unit tests: Altman variant family and distress zones.

Mutation guards (plan §4): market-cap X4 in the variants, X5 kept in Z'',
a cut-off shifted 0.01, the fund guard dropped.
"""

import pytest

from tradingagents.dataflows.quantitative_scores import (
    altman_variant,
    altman_variant_for,
    altman_z_score,
    altman_zone,
)

# x1=0.1, x2=0.2, x3=0.1, x5=0.8; x4 market=600/500=1.2, book=400/500=0.8
FIN = {
    "total_assets": 1000.0,
    "working_capital": 100.0,
    "retained_earnings": 200.0,
    "operating_income": 100.0,
    "total_liabilities": 500.0,
    "market_cap": 600.0,
    "total_equity": 400.0,
    "revenue": 800.0,
}


def test_variant_values_hand_computed():
    assert altman_variant(FIN, "z")["value"] == pytest.approx(2.25)
    # 0.717*0.1 + 0.847*0.2 + 3.107*0.1 + 0.420*0.8 + 0.998*0.8
    assert altman_variant(FIN, "z_prime")["value"] == pytest.approx(1.6862)
    # 6.56*0.1 + 3.26*0.2 + 6.72*0.1 + 1.05*0.8  (X5 dropped)
    assert altman_variant(FIN, "z_double_prime")["value"] == pytest.approx(2.82)
    assert altman_variant(FIN, "z_double_prime_em")["value"] == pytest.approx(6.07)


def test_variants_use_book_equity_not_market_cap():
    # Market-cap X4 would give 0.6*.../1.05*... = 1.8542; book must be used.
    assert altman_variant(FIN, "z_prime")["value"] != pytest.approx(1.8542)
    assert altman_variant(FIN, "z_prime")["x4_basis"].startswith("book equity")


def test_z_double_prime_drops_x5():
    comp = altman_variant(FIN, "z_double_prime")["components"]
    assert "x5" not in comp
    # Keeping X5 would add 0.998*0.8 to Z'': 2.82 + 0.7984 = 3.6184.
    assert altman_variant(FIN, "z_double_prime")["value"] != pytest.approx(3.6184)


def test_missing_book_equity_prints_total_equity_proxy():
    out = altman_variant(FIN, "z_prime")
    assert "total_equity proxy" in out["basis"]
    # A dedicated book_equity line is preferred when present and switches X4.
    with_book = altman_variant({**FIN, "book_equity": 300.0}, "z_prime")
    assert with_book["components"]["x4"] == pytest.approx(0.6)
    assert "proxy" not in with_book["basis"]


def test_altman_z_score_unchanged_for_company_fixture():
    assert altman_z_score(FIN) == pytest.approx(2.25)


@pytest.mark.parametrize(
    "variant,low,high,distress_edge,safe_edge",
    [
        ("z", 1.8, 3.0, (1.79, "distress", 1.81, "grey"), (2.99, "grey", 3.01, "safe")),
        ("z_prime", 1.23, 2.90, (1.22, "distress", 1.24, "grey"), (2.89, "grey", 2.91, "safe")),
        (
            "z_double_prime",
            1.10,
            2.60,
            (1.09, "distress", 1.11, "grey"),
            (2.59, "grey", 2.61, "safe"),
        ),
        (
            "z_double_prime_em",
            1.10,
            2.60,
            (1.09, "distress", 1.11, "grey"),
            (2.59, "grey", 2.61, "safe"),
        ),
    ],
)
def test_zone_boundaries(variant, low, high, distress_edge, safe_edge):
    dl, dlab, gl, glab = distress_edge
    sl, slab, sh, shab = safe_edge
    assert altman_zone(dl, variant)["zone"] == dlab
    assert altman_zone(gl, variant)["zone"] == glab
    assert altman_zone(sl, variant)["zone"] == slab
    assert altman_zone(sh, variant)["zone"] == shab
    # A 0.01 cut-off shift is caught exactly at these edges.
    assert altman_zone(high, variant)["zone"] != "safe"


def test_zone_shape_and_unknown_variant():
    z = altman_zone(3.01, "z")
    assert set(z) == {"zone", "bands", "variant", "basis"}
    assert z["bands"] and "safe" in z["bands"]
    assert altman_zone(3.0, "nope") is None
    assert altman_zone(None, "z") is None


def test_fund_guard_withholds_the_model():
    sel = altman_variant_for(ticker="TEST", identity={"quote_type": "ETF"}, fin=FIN)
    assert sel["variant"] is None
    assert "fund" in sel["reason"].lower()


def test_financial_sector_withholds_the_model():
    sel = altman_variant_for(ticker="BAC", sector="Financial Services", fin=FIN)
    assert sel["variant"] is None
    assert "financial" in sel["reason"].lower()


def test_variant_selection_by_manufacturing():
    mfg = altman_variant_for(ticker="X", fin={**FIN, "inventory": 50.0, "cogs": 300.0})
    assert mfg["variant"] == "z"
    svc = altman_variant_for(ticker="Y", fin=FIN)
    assert svc["variant"] == "z_double_prime"
