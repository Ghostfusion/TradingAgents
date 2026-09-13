"""S2 unit tests: Piotroski paper basis, bands, applicability.

Mutation guards (plan §4): F_ACCRUAL on raw NI instead of the ratio; a missing
signal clamped to 0; a band assigned without both periods.
"""

import pytest

from tradingagents.dataflows.quantitative_scores import (
    piotroski_f_score,
    piotroski_f_score_detailed,
)

SIGNAL_KEYS = (
    "f_roa",
    "f_cfo",
    "f_droa",
    "f_accrual",
    "f_dlever",
    "f_dliquid",
    "f_eq",
    "f_dmargin",
    "f_dturn",
)

BASE = {
    "net_income": {"current": 120.0, "prior": 80.0},
    "total_assets": {"current": 1000.0, "prior": 900.0},
    "operating_cashflow": 150.0,
    "total_debt": {"current": 300.0, "prior": 400.0},
    "current_assets": {"current": 400.0, "prior": 350.0},
    "current_liabilities": {"current": 200.0, "prior": 250.0},
    "shares": {"current": 100.0, "prior": 100.0},
    "revenue": {"current": 1200.0, "prior": 1000.0},
    "cogs": {"current": 700.0, "prior": 650.0},
    "market_cap": 5e9,
}


def _variant(**over):
    fin = {k: (dict(v) if isinstance(v, dict) else v) for k, v in BASE.items()}
    fin.update(over)
    return fin


def test_all_nine_signals_true_on_base_fixture():
    det = piotroski_f_score_detailed(BASE)
    assert set(det["signals"]) == set(SIGNAL_KEYS)
    assert all(det["signals"][k] is True for k in SIGNAL_KEYS)
    assert det["score"] == 9
    assert det["band"]["label"] == "high"


@pytest.mark.parametrize(
    "key,over",
    [
        ("f_roa", {"net_income": {"current": 0.0, "prior": 80.0}}),
        ("f_cfo", {"operating_cashflow": 0.0}),
        ("f_droa", {"net_income": {"current": 120.0, "prior": 200.0}}),
        ("f_accrual", {"operating_cashflow": 0.05}),
        ("f_dlever", {"total_debt": {"current": 500.0, "prior": 400.0}}),
        ("f_dliquid", {"current_assets": {"current": 200.0, "prior": 350.0}}),
        ("f_eq", {"shares": {"current": 120.0, "prior": 100.0}}),
        ("f_dmargin", {"cogs": {"current": 900.0, "prior": 650.0}}),
        ("f_dturn", {"revenue": {"current": 900.0, "prior": 1000.0}}),
    ],
)
def test_each_signal_flips_both_directions(key, over):
    assert piotroski_f_score_detailed(BASE)["signals"][key] is True
    assert piotroski_f_score_detailed(_variant(**over))["signals"][key] is False


def test_accrual_is_the_ratio_test_not_raw_ni():
    # CFO=1.0: ratio test 1.0 > ROA(0.133) is True; raw NI test 1.0 > 120 is
    # False. The detailed signal must be the ratio form.
    det = piotroski_f_score_detailed(_variant(operating_cashflow=1.0))
    assert det["signals"]["f_accrual"] is True


def test_band_low_edge():
    # Exactly one signal (f_dliquid) left true.
    fin = _variant(
        net_income={"current": 0.0, "prior": 80.0},
        operating_cashflow=0.0,
        total_debt={"current": 500.0, "prior": 400.0},
        shares={"current": 120.0, "prior": 100.0},
        revenue={"current": 900.0, "prior": 1000.0},
        cogs={"current": 900.0, "prior": 650.0},
    )
    det = piotroski_f_score_detailed(fin)
    assert det["score"] == 1
    assert det["band"]["label"] == "low"


def test_band_middle_edge():
    fin = _variant(
        total_debt={"current": 500.0, "prior": 400.0},
        current_assets={"current": 200.0, "prior": 350.0},
        shares={"current": 120.0, "prior": 100.0},
        net_income={"current": 120.0, "prior": 200.0},
    )
    det = piotroski_f_score_detailed(fin)
    assert det["score"] == 5
    assert det["band"]["label"] == "middle"


def test_band_prints_the_conventions_it_is_not_using():
    det = piotroski_f_score_detailed(BASE)
    assert "0-2/8-9" in det["band"]["not_used"]
    assert "0-3/7-9" in det["band"]["not_used"]


def test_missing_prior_withholds_band_and_records_substitution():
    det = piotroski_f_score_detailed(_variant(total_assets={"current": 1000.0}))
    assert det["band"] is None
    assert any("ending total assets" in d for d in det["deviations"])
    assert any("band withheld" in d for d in det["deviations"])


def test_missing_signal_is_none_not_zero():
    det = piotroski_f_score_detailed(_variant(total_assets={"current": 1000.0}))
    assert det["signals"]["f_droa"] is None
    assert det["signals"]["f_dturn"] is None


def test_income_basis_deviation_always_recorded():
    det = piotroski_f_score_detailed(BASE)
    assert any("income-before-extraordinary-items" in d for d in det["deviations"])


def test_large_cap_weak_signal_flag():
    det = piotroski_f_score_detailed(_variant(market_cap=50e9))
    assert any("large market cap" in d for d in det["deviations"])


def test_fund_returns_unavailable():
    assert piotroski_f_score_detailed(BASE, classification={"security_type": "ETF"}) is None


def test_legacy_piotroski_f_score_unchanged():
    legacy = {
        "operating_cashflow": 150.0,
        "net_income": 120.0,
        "roa": {"current": 0.10, "prior": 0.05},
        "leverage": {"current": 0.5, "prior": 0.6},
        "current_ratio": {"current": 2.0, "prior": 1.5},
        "shares_issued": 0,
        "gross_margin": {"current": 0.40, "prior": 0.35},
        "asset_turnover": {"current": 1.2, "prior": 1.1},
    }
    assert piotroski_f_score(legacy) == 9
