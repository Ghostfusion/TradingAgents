"""The DCF bridge reads the newest as-reported balance sheet, and says which.

``fetch_ticker`` absorbs the statements with basis="annual", so the canonical
cash/debt pair is the last FISCAL YEAR even when a newer quarter sits in the
vendor payload. GMED 2026-10-14 bridged on the 2025-12-31 pair (cash + ST
investments 557.243m, debt 118.656m) while 2026-06-30 read 595.142m / 111.192m:
net cash 438.587m instead of 483.950m, $0.34/share of fair value, and the
reverse DCF inherited it. The bridge now reads the quarterly payload first and
prints the period it used.
"""

from tradingagents.agents.utils import analysis_tools as at

_CF_Q = (
    "# Cash Flow data for AAA (quarterly)\n"
    "# Data retrieved on: 2026-10-14\n"
    ",2026-06-30,2026-03-31,2025-12-31,2025-09-30\n"
    "Free Cash Flow,176573000.0,162749000.0,202310000.0,204212000.0\n"
)
_BS_Q = (
    "# Balance Sheet data for AAA (quarterly)\n"
    "# Data retrieved on: 2026-10-14\n"
    ",2026-06-30,2026-03-31,2025-12-31\n"
    "Cash Cash Equivalents And Short Term Investments,595142000.0,629851000.0,557243000.0\n"
    "Total Debt,111192000.0,115223000.0,118656000.0\n"
)
_ANNUAL = {
    "cash_and_investments": {"current": 557_243_000.0},
    "total_debt": {"current": 118_656_000.0},
    "market_cap": {"current": 10_159_599_616.0},
    "shares": {"current": 134_252_287.0},
    "beta": {"current": 0.96},
}
_PROV = {
    "cash_and_investments": {"period": "2025/FY"},
    "total_debt": {"period": "2025/FY"},
}


def test_the_bridge_basis_names_its_period():
    cash, debt, cash_basis, debt_basis = at._dcf_cash_debt(
        {
            "cash_and_investments": {"current": 595_142_000.0},
            "total_debt": {"current": 111_192_000.0},
        },
        period="2026/Q2",
    )
    assert (cash, debt) == (595_142_000.0, 111_192_000.0)
    assert cash_basis == "cash + ST investments @ 2026/Q2"
    assert debt_basis == "total debt @ 2026/Q2"


def test_the_basis_is_undated_when_the_period_is_unknown():
    _, _, cash_basis, debt_basis = at._dcf_cash_debt(
        {"cash_and_investments": {"current": 1.0}, "total_debt": {"current": 2.0}}
    )
    assert cash_basis == "cash + ST investments"
    assert debt_basis == "total debt"


def _patch(monkeypatch, balance_sheet_payload):
    def fake_route(method, ticker, *args, **kwargs):
        if method == "get_cashflow":
            return _CF_Q
        if method == "get_balance_sheet":
            return balance_sheet_payload
        return ""

    import tradingagents.dataflows.statement_parsing as sp

    monkeypatch.setattr(at, "route_to_vendor", fake_route)
    monkeypatch.setattr(at, "_dcf_rf", lambda *a, **k: 0.04)
    monkeypatch.setattr(at, "_dcf_last_close", lambda *a, **k: 75.0)
    monkeypatch.setattr(sp, "fetch_ticker", lambda *a, **k: (dict(_ANNUAL), dict(_PROV)))


def test_the_context_prefers_the_newest_quarterly_pair(monkeypatch):
    _patch(monkeypatch, _BS_Q)
    ctx = at._dcf_context("AAA", "2026-10-14")
    assert ctx["error"] is None
    assert ctx["cash"] == 595_142_000.0
    assert ctx["debt"] == 111_192_000.0
    assert ctx["net_cash"] == 483_950_000.0
    # The basis names the period the payload states: a CSV header is a date,
    # a moomoo markdown payload is a quarter label.
    assert "2026-06-30" in ctx["cash_basis"]
    assert "2026-06-30" in ctx["debt_basis"]
    assert "ANNUAL" not in ctx["cash_debt_note"]


def test_the_annual_fallback_is_named(monkeypatch):
    """A quarterly payload without both legs falls back AND says so."""
    _patch(
        monkeypatch,
        "# Balance Sheet data for AAA (quarterly)\n,2026-06-30\nTotal Debt,111192000.0\n",
    )
    ctx = at._dcf_context("AAA", "2026-10-14")
    assert ctx["error"] is None
    assert ctx["cash"] == 557_243_000.0
    assert ctx["debt"] == 118_656_000.0
    assert ctx["net_cash"] == 438_587_000.0
    assert "2025/FY" in ctx["cash_basis"]
    assert "ANNUAL statement" in ctx["cash_debt_note"]
