"""CapEx-allocation read tests (pure module + hermetic tool).

Adjudication artifact of the AMZN 2026-09-09 report-review loop: a negative
trailing FCF alone must NOT read as a quality verdict; the module separates
PRODUCTIVE_INVESTMENT (reinvestment) from OVERINVESTMENT / DISTRESS and is
pure / None-safe (never fabricates).
"""

from tradingagents.agents.utils import value_dip_tools as V
from tradingagents.strategies.capex_quality import capex_quality_read

B = 1e9


def _amzn_fy25():
    """AMZN FY21-FY25 annual series (raw $), positive FCF, high funding."""
    mul = lambda s: [v * B for v in s]  # noqa: E731
    return (
        mul([469.8, 514.0, 574.8, 638.0, 716.9]),   # revenue
        mul([46.3, 46.8, 84.9, 115.9, 139.5]),      # ocf
        mul([59.1, 60.8, 61.5, 83.1, 91.0]),        # capex
        mul([22.0, 16.4, 39.2, 58.4, 66.0]),        # nopat
        mul([290.0, 330.0, 380.0, 430.0, 480.0]),   # invested capital
        mul([34.2, 38.3, 45.3, 59.3, 76.7]),        # D&A
    )


def test_harvest_regime_positive_fcf():
    rev, ocf, capex, nopat, ic, da = _amzn_fy25()
    out = capex_quality_read(rev, ocf, capex, nopat, ic, da,
                             market_cap=2721.0 * B, wacc=0.12)
    assert out["fcf"] > 0
    assert out["regime"] == "HARVEST"
    assert out["score"] is not None and 0 <= out["score"] <= 100
    assert out["penalty_points"] == 0
    # funding cover well above 1.0
    assert out["funding"] > 1.5


def _b(*vals):
    return [v * B for v in vals]


def test_negative_fcf_low_funding_is_distress():
    rev = _b(100.0, 120.0, 140.0, 160.0)
    ocf = _b(18.0, 19.0, 20.0, 21.0)
    capex = _b(25.0, 30.0, 35.0, 40.0)            # funding ~0.5
    nopat = _b(10.0, 11.0, 12.0, 13.0)
    ic = _b(100.0, 110.0, 120.0, 130.0)
    out = capex_quality_read(rev, ocf, capex, nopat, ic, market_cap=300.0 * B)
    assert out["fcf"] < 0
    assert out["regime"] == "DISTRESS"
    assert out["penalty_points"] in (10, 20, 30)


def test_overinvestment_when_spread_negative():
    """FCF<0 with a negative incremental-ROIC spread => OVERINVESTMENT, not
    PRODUCTIVE (the distinction the external review demanded)."""
    rev = _b(100.0, 130.0, 160.0, 200.0)
    ocf = _b(20.0, 22.0, 24.0, 25.0)
    capex = _b(15.0, 25.0, 35.0, 38.0)            # funding 25/38 ~ 0.66 (>= 0.6)
    nopat = _b(10.0, 11.0, 12.0, 12.5)            # flat NOPAT => dNOPAT tiny
    ic = _b(100.0, 120.0, 150.0, 210.0)           # big IC jump
    out = capex_quality_read(rev, ocf, capex, nopat, ic, market_cap=300.0 * B, wacc=0.12)
    assert out["fcf"] < 0
    assert out["regime"] == "OVERINVESTMENT"


def test_productive_investment_when_spread_positive():
    """FCF<0 but incremental ROIC still above WACC => PRODUCTIVE_INVESTMENT,
    not a sell signal - the AMZN TTM Jun-26 adjudication (funding ~0.96)."""
    rev = _b(469.8, 514.0, 574.8, 638.0, 716.9, 775.7)
    ocf = _b(46.3, 46.8, 84.9, 115.9, 139.5, 161.4)
    capex = _b(59.1, 60.8, 61.5, 83.1, 91.0, 169.0)
    nopat = _b(22.0, 16.4, 39.2, 58.4, 66.0, 70.0)
    ic = _b(290.0, 330.0, 380.0, 430.0, 480.0, 540.0)
    da = _b(34.2, 38.3, 45.3, 59.3, 76.7, 84.0)
    out = capex_quality_read(rev, ocf, capex, nopat, ic, da,
                             market_cap=2721.0 * B, wacc=0.12)
    assert out["fcf"] < 0
    assert out["funding"] > 0.9
    assert out["regime"] == "PRODUCTIVE_INVESTMENT"
    assert out["penalty_points"] is not None and out["penalty_points"] <= 5


def test_none_safe_and_no_fabrication():
    """All-None series => regime n/a, no crash, no invented numbers."""
    out = capex_quality_read([None] * 5, [None] * 5, [None] * 5, [None] * 5)
    assert out["regime"] == "n/a"
    assert out["score"] is None
    assert out["fcf"] is None
    assert out["fcf_yield"] is None


def test_short_invested_capital_degrades_incr_roic_only():
    """No IC series => incremental ROIC / spread n/a, but FCF/regime still
    computed (partial read is honest, not dropped)."""
    rev = _b(100, 130, 160)
    ocf = _b(20, 22, 24)
    capex = _b(15, 25, 35)
    nopat = _b(10, 11, 12)
    out = capex_quality_read(rev, ocf, capex, nopat, market_cap=300.0 * B)
    assert out["incr_roic"] is None
    assert out["spread"] is None
    assert out["fcf"] is not None
    assert out["regime"] in ("HARVEST", "PRODUCTIVE", "INVESTMENT_WATCH")


# ---------------------------------------------------------------------------
# Hermetic tool-level test (annual statement series -> rendered read)
# ---------------------------------------------------------------------------

def _period_md(lab, rows):
    return "\n".join(
        [f"### {lab}  (currency: USD)",
         "| Item | Value | YoY | QoQ |",
         "| --- | --- | --- | --- |",
         *[f"| {k} | {v} | -- | -- |" for k, v in rows],
         ""]
    )


def _annual_payloads():
    years = ["FY2025", "FY2024", "FY2023", "FY2022"]
    cf = [("Operating Cash Flow", "139.5B"), ("Capital Expenditure", "-91.0B"),
          ("Depreciation Amortization", "76.7B")]
    inc = [("Total Revenue", "716.9B"), ("Operating Income", "66.0B"),
           ("Tax Rate For Calcs", "0.24")]
    bal = [("Total Debt", "480.0B"), ("Stockholders Equity", "540.0B"),
           ("Cash And Cash Equivalents", "90.0B")]
    return {
        "get_cashflow": "\n".join(_period_md(y, cf) for y in years),
        "get_income_statement": "\n".join(_period_md(y, inc) for y in years),
        "get_balance_sheet": "\n".join(_period_md(y, bal) for y in years),
    }


def test_get_capex_quality_renders_tool(monkeypatch):
    monkeypatch.setattr(
        "tradingagents.dataflows.statement_parsing.fetch_ticker",
        lambda t, d: {"market_cap": 2.721e12},
    )
    payloads = _annual_payloads()

    def side(method, *a, **k):
        return payloads.get(method, "NO_DATA_AVAILABLE")

    monkeypatch.setattr(V, "route_to_vendor", side)
    out = V.get_capex_quality.invoke({"ticker": "AMZN", "current_date": "2026-09-09"})
    assert "capex quality AMZN" in out
    assert "regime=" in out
    assert "funding=" in out
    assert "penalty=" in out
    assert "incr_ROIC=" in out
    # FCF = 139.5 - 91.0 = 48.5B > 0 => HARVEST on this fixture.
    assert "HARVEST" in out


def test_get_capex_quality_degrades_without_statements(monkeypatch):
    monkeypatch.setattr(
        "tradingagents.dataflows.statement_parsing.fetch_ticker",
        lambda t, d: {},
    )
    monkeypatch.setattr(V, "route_to_vendor", lambda *a, **k: "NO_DATA_AVAILABLE")
    out = V.get_capex_quality.invoke({"ticker": "AMZN", "current_date": "2026-09-09"})
    assert "unavailable" in out.lower()
