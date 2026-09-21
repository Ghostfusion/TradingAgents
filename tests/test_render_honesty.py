"""Honest rendering of unmeasurable values (defect-audit batch C).

Three related defects are pinned here:

1. ``analysis_tools`` rendered float-or-None risk metrics with ``or 0``, so an
   *unmeasured* metric (fewer than 2 downside returns, a hypothesis test that
   raised, a neutral GARCH fit) printed as a hard ``0.00%`` / ``0.000`` - which
   reads as a measurement ("no downside risk", "normality decisively
   rejected"), the opposite of the truth. A real ``0.0`` measurement must still
   render as ``0``.
2. ``_dcf_beta`` / ``_dcf_cash_debt`` substituted ``1.0`` / ``0.0`` for a
   missing vendor line while the row still claimed "provider-derived", making
   an assumption indistinguishable from a measurement (and silently moving
   WACC / fair value). The assumption must be labelled.
3. ``_beat_streak_identity``'s private word map stopped at "six", so a
   "seven/eight straight >K% beats" claim parsed as ``None`` and the check
   silently returned no verdict - even though the sibling double-digit map
   covers seven/eighth.

Each test fails on the pre-fix code and passes after.
"""

from __future__ import annotations

from tradingagents.agents.utils import analysis_tools as T, report_verifier as rv


def _flat_closes(n: int) -> list[float]:
    """Deterministic price history with enough bars for every tool below."""
    return [100.0 + 0.4 * i for i in range(n)]


# --------------------------------------------------------------------------
# (a) None risk metrics render 'n/a'; a real 0.0 still renders as 0.
# --------------------------------------------------------------------------


def test_downside_read_renders_unmeasured_metrics_as_na(monkeypatch):
    from tradingagents.strategies import rate_utils

    monkeypatch.setattr(T, "_ohlcv", lambda t: {"closes": _flat_closes(30)})
    # semi_deviation/avg_shortfall measured; downside_deviation/shortfall_prob
    # unmeasured for this series. Mixing both proves None != 0.0.
    monkeypatch.setattr(
        rate_utils,
        "downside_measures",
        lambda returns, target=0.0: {
            "semi_deviation": None,
            "downside_deviation": 0.0,
            "regret": None,
            "shortfall_prob": None,
            "avg_shortfall": 0.0,
            "n": len(returns),
        },
    )
    monkeypatch.setattr(rate_utils, "kappa_ratio", lambda *a, **k: None)
    monkeypatch.setattr(rate_utils, "lower_partial_moment", lambda *a, **k: None)

    out = T.get_downside_read.invoke({"ticker": "AAPL"})

    assert "semi_dev=n/a" in out
    assert "shortfall_prob=n/a" in out
    # A real 0.0 measurement must NOT be turned into 'n/a'.
    assert "downside_dev=0.00%" in out
    assert "avg_shortfall=0.00%" in out


def test_horizon_var_renders_unmeasured_var_as_na(monkeypatch):
    from tradingagents.strategies import book_risk

    monkeypatch.setattr(T, "_ohlcv", lambda t: {"closes": _flat_closes(80)})
    monkeypatch.setattr(
        book_risk,
        "var_cvar_horizon",
        lambda returns, horizon_days, alpha=0.95: {
            "emp_var": None,
            "emp_cvar": None,
            "param_var": 0.0,
            "param_cvar": None,
            "scaling_valid": False,
            "n": len(returns),
        },
    )

    out = T.get_horizon_var.invoke({"ticker": "AAPL"})

    assert "emp_var=n/a" in out
    assert "emp_cvar=n/a" in out
    assert "param_var=0.00%" in out


def test_normality_renders_unmeasured_p_values_as_na(monkeypatch):
    from tradingagents.strategies import statistical

    monkeypatch.setattr(T, "_ohlcv", lambda t: {"closes": _flat_closes(40)})
    monkeypatch.setattr(
        statistical,
        "normality",
        lambda returns: {
            "jarque_bera": {"p_value": None},
            "shapiro_wilk": {"p_value": 0.0},
            "normal": False,
        },
    )

    out = T.get_normality.invoke({"ticker": "AAPL"})

    assert "jarque_bera_p=n/a" in out
    assert "shapiro_p=0.000" in out


# --------------------------------------------------------------------------
# (b) Assumed DCF inputs must be labelled as assumptions.
# --------------------------------------------------------------------------

_CF_CSV = """# Cash Flow data for AAPL (annual)

,2025-09-30,2024-09-30,2023-09-30,2022-09-30
Operating Cash Flow,110000000000,95000000000,85000000000,78000000000
Capital Expenditure,-15000000000,-12000000000,-11000000000,-10000000000
Free Cash Flow,95000000000,83000000000,69000000000,68000000000
"""


def _patch_dcf_vendors(monkeypatch, side):
    from tradingagents.dataflows import statement_parsing as _sp

    monkeypatch.setattr(T, "route_to_vendor", side)
    monkeypatch.setattr(_sp, "route_to_vendor", side)
    monkeypatch.setattr(T, "_ohlcv", lambda t: {"closes": [200.0, 205.0, 210.0]})
    # `fetch_ticker` gap-fills from Finnhub directly (not through
    # route_to_vendor), and Finnhub's basic financials carry a real `beta`.
    # Pin that leg so the beta tests below assert WHICH source supplied the
    # number instead of depending on whether the live vendor answered.
    monkeypatch.setattr(
        "tradingagents.dataflows.finnhub.get_basic_financials_finnhub",
        lambda *a, **k: "",
    )


def _dcf_side(fundamentals: str, balance: str = "Cash Cash Equivalents: 60000000000\nTotal Debt: 110000000000"):
    def side(method, *a, **k):
        return {
            "get_cashflow": _CF_CSV,
            "get_fundamentals": fundamentals,
            "get_balance_sheet": balance,
            "get_macro_indicators": "## FRED 10Y\nLatest: 4.2",
            "get_stock_data": "",
        }.get(method, "")

    return side


def test_dcf_without_provider_beta_labels_the_assumption(monkeypatch):
    _patch_dcf_vendors(monkeypatch, _dcf_side("Market Cap: 3000000000000"))

    out = T.get_dcf_valuation.invoke({"ticker": "AAPL", "current_date": "2026-08-20"})

    assert "dcf AAPL" in out
    assert "beta=1.00 (assumed, no provider beta)" in out


def test_dcf_with_provider_beta_renders_the_measured_number(monkeypatch):
    _patch_dcf_vendors(monkeypatch, _dcf_side("Beta: 1.35\nMarket Cap: 3000000000000"))

    out = T.get_dcf_valuation.invoke({"ticker": "AAPL", "current_date": "2026-08-20"})

    assert "dcf AAPL" in out
    assert "beta=1.35" in out
    assert "assumed" not in out


def test_dcf_labels_assumed_cash_and_debt_when_vendor_omits_them(monkeypatch):
    _patch_dcf_vendors(
        monkeypatch,
        _dcf_side("Beta: 1.35\nMarket Cap: 3000000000000", balance=""),
    )

    out = T.get_dcf_valuation.invoke({"ticker": "AAPL", "current_date": "2026-08-20"})

    assert "dcf AAPL" in out
    assert "cash/debt assumed 0 (not reported)" in out


# --------------------------------------------------------------------------
# (c) Word-count streak claims above 'six' are not silently skipped.
# --------------------------------------------------------------------------


def test_beat_streak_identity_parses_word_above_six():
    text = (
        "Momentum: seven straight >40% EPS beats.\n"
        "| Period | Date | EPS est | EPS act | Surprise% | Day move | Implied |\n"
        "| 2027/Q2 |2026-09-01 |4.4029 |6.34 |+44.0 |+15.8% |10.9% |\n"
        "| 2027/Q1 |2026-05-28 |2.61 |5.24 |+100.8 |+32.8% |12.5% |\n"
        "| 2026/Q4 |2026-02-20 |3.10 |5.01 |+55.0 |+9.1% |8.0% |\n"
    )

    claims = rv._beat_streak_identity(text)

    assert len(claims) == 1
    assert claims[0].status == "INTERNAL_CONFLICT"
    assert "3 consecutive" in claims[0].claim


# --------------------------------------------------------------------------
# (d) The DCF leaf must carry its own EV -> equity bridge, and an assumed
#     beta must show what it is worth.
# --------------------------------------------------------------------------


def _leaf_floats(out: str) -> dict:
    import re as _re

    vals = {}
    for key in ("fair_value", "equity", "shares", "cash", "debt", "net_debt", "ev"):
        m = _re.search(rf"\b{key}=([-\d,.]+)", out)
        if m:
            vals[key] = float(m.group(1).replace(",", ""))
    return vals


def test_dcf_leaf_carries_the_bridge_it_used(monkeypatch):
    """A fair value with an invisible bridge is not reproducible from itself.
    MSFT 2026-09-16 printed 124.80 while the same FCF at an equivalent WACC
    gives 123.57 (cash + ST investments less TOTAL debt) or 116.22 (cash and
    equivalents less total debt): an $8.58/share swing that no reader could
    see, because `cash`, `debt` and `equity` were not in the leaf."""
    _patch_dcf_vendors(
        monkeypatch,
        _dcf_side(
            "Beta: 1.35\nMarket Cap: 3000000000000",
            balance=(
                "Cash and Cash Equivalents: 20935000000\n"
                "Cash Cash Equivalents And Short Term Investments: 76651000000\n"
                "Total Debt: 56826000000\n"
            ),
        ),
    )

    out = T.get_dcf_valuation.invoke({"ticker": "AAPL", "current_date": "2026-08-20"})

    # Cash INCLUDING short-term investments is the leg a net-debt statement
    # needs, and it must be named.
    assert "cash=76,651,000,000" in out
    assert "debt=56,826,000,000" in out
    assert "net_debt=19,825,000,000" in out
    assert "bridge=(cash + ST investments - total debt)" in out
    # ...and the three printed numbers must reproduce the printed fair value.
    v = _leaf_floats(out)
    assert abs(v["equity"] / v["shares"] - v["fair_value"]) < 0.01
    assert abs((v["cash"] - v["debt"]) - v["net_debt"]) < 1.0


def test_dcf_falls_back_to_the_narrow_cash_row_and_names_that_basis(monkeypatch):
    _patch_dcf_vendors(
        monkeypatch,
        _dcf_side(
            "Beta: 1.35\nMarket Cap: 3000000000000",
            balance="Cash and Cash Equivalents: 60000000000\nTotal Debt: 110000000000\n",
        ),
    )

    out = T.get_dcf_valuation.invoke({"ticker": "AAPL", "current_date": "2026-08-20"})

    assert "cash=60,000,000,000" in out
    assert "bridge=(cash and equivalents (no ST-investments row) - total debt)" in out


def test_dcf_shows_what_an_assumed_beta_is_worth(monkeypatch):
    """The assumed-beta path is a WACC assumption, and it moved MSFT's fair
    value 124.80 -> 116.68 against the provider beta the same run already had
    (1.108). Print the sensitivity instead of one point value."""
    _patch_dcf_vendors(monkeypatch, _dcf_side("Market Cap: 3000000000000"))

    out = T.get_dcf_valuation.invoke({"ticker": "AAPL", "current_date": "2026-08-20"})

    assert "beta=1.00 (assumed, no provider beta)" in out
    assert "beta_sensitivity=(0.8->" in out
    v = _leaf_floats(out)
    # Every printed leg is a real fair value, and the sensitivity straddles it.
    legs = {
        float(a): float(b)
        for a, b in (pair.split("->") for pair in
                     out.split("beta_sensitivity=(")[1].split(")")[0].split())
    }
    assert legs[1.1] < v["fair_value"] < legs[0.8]


def test_dcf_with_a_provider_beta_prints_no_sensitivity(monkeypatch):
    _patch_dcf_vendors(monkeypatch, _dcf_side("Beta: 1.35\nMarket Cap: 3000000000000"))

    out = T.get_dcf_valuation.invoke({"ticker": "AAPL", "current_date": "2026-08-20"})

    assert "beta=1.35" in out
    assert "beta_sensitivity" not in out
