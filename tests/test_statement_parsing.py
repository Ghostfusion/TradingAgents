"""Vendor-output -> canonical parsing layer (tradingagents.dataflows).

These parsers were moved out of ``scripts/value_screener.py`` so agent tools
can use them inside the *installed* CLI, whose wheel ships only
``tradingagents*`` and ``cli*`` (no ``scripts/`` on sys.path). The suite
guards that contract: the package module must never depend on ``scripts`` at
runtime, ``scripts.value_screener`` must keep re-exporting the same names, and
the canonical aliases must cover the fields the DCF / fcf-yield / z-score
tools need (market cap, beta, shares).
"""

import pytest

from tradingagents.dataflows import statement_parsing as sp


@pytest.mark.unit
def test_module_imports_and_parsers_work_with_scripts_blocked(monkeypatch):
    """The package parsers never touch scripts/ (the installed-CLI contract)."""

    class _Block:
        """Raises for any 'scripts' import - simulates the wheel install."""

        def find_spec(self, name, *_a, **_k):
            if name == "scripts" or name.startswith("scripts."):
                raise ModuleNotFoundError(f"No module named {name!r}")
            return None

    blocker = _Block()
    inserted = 0
    import sys

    sys.meta_path.insert(0, blocker)
    inserted = 1
    try:
        assert sp._first_number("$1.2B") == 1.2e9
        assert sp._percent_fraction("12.5%") == 0.125
        tables = sp._markdown_period_tables(
            "### Cash Flow (FY 2025)\n"
            "| Item | FY2025 | FY2024 |\n| --- | --- |\n"
            "| Operating Cash Flow | 110000000000 | 95000000000 |\n"
        )
        assert len(tables) == 1
        assert tables[0][1]["Operating Cash Flow"] == 110000000000
    finally:
        if inserted:
            import contextlib

            contextlib.suppress(ValueError)
            with contextlib.suppress(ValueError):
                sys.meta_path.remove(blocker)


@pytest.mark.unit
def test_canonical_aliases_beta_shares_and_market_cap():
    canonical = sp._canonicalize(
        "Beta: 1.35\nMarket Cap: 3000000000000\nShares Outstanding: 15000000000"
    )
    assert canonical.get("beta") == 1.35
    assert canonical.get("shares") == 15_000_000_000.0
    assert canonical.get("market_cap") == 3_000_000_000_000.0


@pytest.mark.unit
def test_canonicalize_markdown_picks_period_rows():
    md = (
        "### Income Statement (FY 2025)\n"
        "| Item | FY2025 | FY2024 |\n| --- | --- |\n"
        "| Diluted EPS | 2.90 | 1.80 |\n"
        "### Balance Sheet (FY 2025)\n"
        "| Item | FY2025 | FY2024 |\n| --- | --- |\n"
        "| Total Assets | 180000000000 | 150000000000 |\n"
    )
    c = sp._canonicalize(md)
    assert c["eps"] == 2.90  # single table -> flat float (no "prior" row)
    assert c["total_assets"] == 180000000000.0


@pytest.mark.unit
def test_markdown_period_tables_sorted_newest_first():
    tables = sp._markdown_period_tables(
        "### Cash Flow (FY 2024)\n| Item | FY2024 |\n| --- | --- |\n| FCF | 1 |\n"
        "### Cash Flow (FY 2025)\n| Item | FY2025 |\n| --- | --- |\n| FCF | 2 |\n"
    )
    assert [t[0] for t in tables] == ["Cash Flow (FY 2025)", "Cash Flow (FY 2024)"]


@pytest.mark.unit
def test_parse_csv_statements_takes_first_column():
    """yfinance statement columns are newest-first, so the FIRST numeric cell
    is the latest period (the old rightmost pick returned the OLDEST)."""
    rows = sp._parse_csv_statements(
        ",2025-09-30,2024-09-30,2023-09-30\n"
        "Free Cash Flow,95000000000,83000000000,69000000000\n"
    )
    assert rows["Free Cash Flow"] == 95_000_000_000.0  # newest column


@pytest.mark.unit
def test_fetch_and_screen_importable():
    assert callable(sp.fetch_ticker)
    assert callable(sp.screen_ticker)
    assert sp.screen_ticker.__name__ == "screen_ticker"


@pytest.mark.unit
def test_scripts_value_screener_re_exports_parsers():
    """scripts/ keeps the same names for the backend CLI + value_screener."""
    import scripts.value_screener as vs

    assert vs._first_number("$3.5B") == 3.5e9
    assert vs._period_year("2025/FY") == 2025
    assert vs._latest({"current": 1.0, "prior": 2.0}) == 1.0
    assert vs.screen_ticker.__name__ == "screen_ticker"
    assert vs._canonicalize("Beta: 1.35\nMarket Cap: 3000000000000").get("beta") == 1.35


@pytest.mark.unit
def test_income_series_csv_form():
    csv_payload = (
        ",2025-09-30,2024-09-30,2023-09-30,2022-09-30\n"
        "Total Revenue,416160000000,391040000000,383290000000,394330000000\n"
        "Operating Income,133050000000,123220000000,114300000000,119440000000\n"
        "Net Income,112010000000,93740000000,97000000000,99800000000\n"
    )
    s = sp.income_series(csv_payload)
    assert s is not None and len(s) == 4
    assert s[0]["year"] == 2022  # oldest first
    assert s[-1]["year"] == 2025
    assert s[-1]["revenue"] == pytest.approx(416.16e9, rel=0.01)
    assert s[-1]["ebit"] == pytest.approx(133.05e9, rel=0.01)
    assert s[-1]["net_income"] == pytest.approx(112.01e9, rel=0.01)


@pytest.mark.unit
def test_income_series_degraded_forms():
    assert sp.income_series("") is None
    assert sp.income_series("NO_DATA_AVAILABLE: x") is None
    assert sp.income_series("not a statement at all") is None


@pytest.mark.unit
def test_enrich_screen_ratios_derives_piotroski_inputs():
    fin = {
        "net_income": {"current": 100e6, "prior": 80e6},
        "total_assets": {"current": 1000e6, "prior": 900e6},
        "total_equity": {"current": 500e6, "prior": 450e6},
        "current_assets": {"current": 300e6, "prior": 280e6},
        "current_liabilities": {"current": 150e6, "prior": 140e6},
        "revenue": {"current": 800e6, "prior": 700e6},
        "cogs": {"current": 500e6, "prior": 450e6},
        "cost_of_revenue": {"current": 500e6, "prior": 450e6},
        "shares": {"current": 1e9, "prior": 1.05e9},
    }
    sp.enrich_screen_ratios(fin)
    assert fin["roa"]["current"] == pytest.approx(0.10, rel=0.01)
    assert fin["roa"]["prior"] == pytest.approx(0.0889, rel=0.01)
    assert fin["current_ratio"]["current"] == pytest.approx(2.0)
    assert fin["gross_margin"]["current"] == pytest.approx(0.375, rel=0.01)
    assert fin["asset_turnover"]["current"] == pytest.approx(0.8, rel=0.01)
    # share reduction -> negative shares_issued (repurchase) for the F score.
    assert fin["shares_issued"] == pytest.approx(-50e6, rel=0.01)


@pytest.mark.unit
def test_screen_ticker_computes_piotroski_f_score():
    fin = {
        "market_cap": 3e9,
        "net_income": {"current": 100e6, "prior": 80e6},
        "total_assets": {"current": 1000e6, "prior": 900e6},
        "total_equity": {"current": 500e6, "prior": 450e6},
        "current_assets": {"current": 300e6, "prior": 280e6},
        "current_liabilities": {"current": 150e6, "prior": 140e6},
        "revenue": {"current": 800e6, "prior": 700e6},
        "cogs": {"current": 500e6, "prior": 450e6},
        "operating_cashflow": {"current": 120e6, "prior": 90e6},
        "shares": {"current": 1e9, "prior": 1.05e9},
    }
    sp.enrich_screen_ratios(fin)
    from tradingagents.dataflows.quantitative_scores import piotroski_f_score

    score = piotroski_f_score(fin)
    assert score is not None
    assert 0 <= score <= 9
    assert score > 0  # previously n/a because the ratio inputs were missing


def test_sane_revenue_yoy_guards_degenerate_base():
    """Regression (MSFT 2026-09-08): a vendor revenue_yoy of 17.79 (percent-
    scaled) rendered as +1779%. The guard must return n/a for |YoY| > 300%
    and fall back to the revenue pair when that base is safe."""
    assert sp.sane_revenue_yoy({"revenue_yoy": 17.79, "revenue": {"current": 331.8e9, "prior": 281.7e9}}) \
        == pytest.approx((331.8e9 - 281.7e9) / 281.7e9)
    assert sp.sane_revenue_yoy({"revenue_yoy": 17.79}) is None
    assert sp.sane_revenue_yoy({"revenue_yoy": 0.1779}) == pytest.approx(0.1779)


def test_screen_ticker_uses_sane_revenue_yoy():
    fin = {
        "revenue_yoy": 17.79,
        "revenue": {"current": 331.8e9, "prior": 281.7e9},
        "eps_yoy": 0.317,
        "eps": {"current": 4.81, "prior": 3.65},
        "market_cap": 3.6e12,
        "total_assets": 758e9,
        "total_liabilities": 316e9,
        "current_assets": 207.7e9,
        "total_equity": 442e9,
        "net_income": 133.7e9,
    }
    row = sp.screen_ticker("MSFT", fin)
    assert row["revenue_yoy"] is not None
    assert abs(row["revenue_yoy"]) <= 3.0
    assert row["revenue_yoy"] == pytest.approx((331.8e9 - 281.7e9) / 281.7e9)


def test_sane_revenue_yoy_percent_scaled_resolves_via_pair():
    """Regression (QCOM 2026-09-08): a percent-scaled vendor revenue_yoy of
    1.88 (rendered 188%) vs the true +1.88%. The pair recompute must win over
    the artifact, even though |1.88| <= 3.0."""
    fin = {
        "revenue_yoy": 1.88,
        "revenue": {"current": 44.07e9, "prior": 43.25e9},
    }
    # True YoY = (44.07-43.25)/43.25 = 1.9%
    out = sp.sane_revenue_yoy(fin)
    assert out == pytest.approx(0.01895, rel=0.02)
    assert out < 0.03  # not 1.88


def test_sane_revenue_yoy_percent_scaled_without_pair():
    """No revenue pair to arbitrate -> a >100% claimed YoY is treated as
    percent-scaled (1.88 == 1.88%)."""
    assert sp.sane_revenue_yoy({"revenue_yoy": 1.88}) == pytest.approx(0.0188)
    # A sane vendor value in the plausible band (0.4 = 40% growth, no pair)
    # passes through unchanged.
    assert sp.sane_revenue_yoy({"revenue_yoy": 0.4}) == pytest.approx(0.4)


@pytest.mark.unit
def test_fetch_ticker_provenance_records_source_basis_and_period(monkeypatch):
    """NVDA 2026-09-12 (D1): the merge overwrote up to four vendor payloads per
    key with no record of which period or vendor won, so a derived ratio could
    not state its basis. ``with_provenance=True`` returns that record; the
    default call keeps returning the plain dict so existing callers are
    unaffected."""
    annual_income = (
        "# Income Statement data for TST (annual)\n"
        "# Data retrieved on: 2026-09-12 00:00:00\n\n"
        ",2026-01-31,2025-01-31\n"
        "Total Revenue,215940000000.0,130500000000.0\n"
        "Net Income,120070000000.0,72880000000.0\n"
    )
    balance = (
        "# Balance Sheet data for TST (annual)\n"
        "# Data retrieved on: 2026-09-12 00:00:00\n\n"
        ",2026-01-31,2025-01-31\n"
        "Total Assets,206800000000.0,140740000000.0\n"
        "Stockholders Equity,157290000000.0,100130000000.0\n"
    )

    def _fake(method, *args, **kwargs):
        if method == "get_income_statement":
            return annual_income
        if method == "get_balance_sheet":
            return balance
        raise RuntimeError("no vendor for " + method)

    monkeypatch.setattr(sp, "route_to_vendor", _fake)

    fin, prov = sp.fetch_ticker("TST", "2026-09-12", with_provenance=True)
    assert prov["net_income"] == {
        "source": "get_income_statement",
        "basis": "annual",
        "period": "2026-01-31",
    }
    assert prov["total_assets"]["period"] == "2026-01-31"
    assert fin["net_income"] == pytest.approx(120070000000.0)

    # Default call: the plain dict, unchanged for every existing caller.
    plain = sp.fetch_ticker("TST", "2026-09-12")
    assert isinstance(plain, dict) and plain["net_income"] == pytest.approx(120070000000.0)


@pytest.mark.unit
def test_trailing_twelve_months_sums_only_a_full_window(monkeypatch):
    """A partial window must be ABSENT, never presented as a year (D1)."""
    quarterly = (
        "# Income Statement data for TST (quarterly)\n"
        "# Data retrieved on: 2026-09-12 00:00:00\n\n"
        ",2026-07-31,2026-04-30,2026-01-31\n"
        "Total Revenue,96221000000.0,81615000000.0,68127000000.0\n"
        "Net Income,59688000000.0,58320000000.0,42960000000.0\n"
    )

    def _fake(method, *args, **kwargs):
        return quarterly if method == "get_income_statement" else "DATA_UNAVAILABLE: no cashflow"

    monkeypatch.setattr(sp, "route_to_vendor", _fake)

    ttm = sp.trailing_twelve_months("TST", "2026-09-12")
    assert ttm["periods"] == []
    assert "net_income_ttm" not in ttm      # three quarters is not a year
    assert ttm["complete"] is False

    four = quarterly.replace(",2026-01-31\n", ",2026-01-31,2025-10-31\n").replace(
        "68127000000.0\n", "68127000000.0,57006000000.0\n"
    ).replace("42960000000.0\n", "42960000000.0,31910000000.0\n")
    monkeypatch.setattr(sp, "route_to_vendor", lambda method, *a, **k: four)
    full = sp.trailing_twelve_months("TST", "2026-09-12")
    assert full["periods"][0] == "2026-07-31"
    assert full["net_income_ttm"] == pytest.approx(192878000000.0)
    assert full["complete"] is True
