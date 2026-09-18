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
        # The payload is a yfinance-style CSV whose header is a bare date, so
        # the kind is unstated rather than assumed - and no conflict is claimed
        # on the strength of a column layout.
        "observed_kind": "unstated",
        "basis_conflict": False,
    }
    assert prov["total_assets"]["period"] == "2026-01-31"
    assert fin["net_income"] == pytest.approx(120070000000.0)

    # Default call: the plain dict, unchanged for every existing caller.
    plain = sp.fetch_ticker("TST", "2026-09-12")
    assert isinstance(plain, dict) and plain["net_income"] == pytest.approx(120070000000.0)


@pytest.mark.unit
def test_fetch_ticker_flags_a_quarterly_payload_under_an_annual_request(monkeypatch):
    """AMZN 2026-09-14: the merge asked the statement vendors for ``annual``
    and stamped a flat ``annual`` on whatever came back, so FY-annual rows were
    combined with TTM quarters (EV/EBIT 32.79 -> -30551.06) and nothing
    recorded the disagreement. The payload's own period now decides
    ``observed_kind``, and a contradiction sets ``basis_conflict``."""
    quarterly_income = (
        "### Income Statement (2026/Q2)\n"
        "| Item | Q2 |\n| --- | --- |\n"
        "| Total Revenue | 96,221,000,000 |\n"
        "| Net Income | 59,688,000,000 |\n"
    )
    annual_balance = (
        "### Balance Sheet (FY 2025)\n"
        "| Item | FY2025 |\n| --- | --- |\n"
        "| Total Assets | 206,800,000,000 |\n"
        "| Stockholders Equity | 157,290,000,000 |\n"
    )

    def _fake(method, *args, **kwargs):
        if method == "get_income_statement":
            return quarterly_income
        if method == "get_balance_sheet":
            return annual_balance
        raise RuntimeError("no vendor for " + method)

    monkeypatch.setattr(sp, "route_to_vendor", _fake)

    _fin, prov = sp.fetch_ticker("TST", "2026-09-14", with_provenance=True)
    income = {k: v for k, v in prov.items() if v["source"] == "get_income_statement"}
    balance = {k: v for k, v in prov.items() if v["source"] == "get_balance_sheet"}
    assert income and balance  # both payloads were parsed, not empty dicts
    assert {v["observed_kind"] for v in income.values()} == {"quarterly"}
    assert all(v["basis_conflict"] for v in income.values())
    assert all(v["period"] == "Income Statement (2026/Q2)" for v in income.values())
    assert {v["observed_kind"] for v in balance.values()} == {"annual"}
    assert not any(v["basis_conflict"] for v in balance.values())


@pytest.mark.unit
def test_fetch_ticker_keeps_the_basis_label_when_the_merge_cannot_see_a_kind(monkeypatch):
    """A bare date header states no kind: an annual request against it is NOT a
    conflict, so the merge never cries wolf over a vendor's column layout.
    Only an explicit quarterly/TTM label is evidence."""
    csv_payload = (
        "# Income Statement data for TST (annual)\n\n"
        ",2026-01-31,2025-01-31\n"
        "Total Revenue,215940000000.0,130500000000.0\n"
    )
    monkeypatch.setattr(sp, "route_to_vendor", lambda *a, **kw: csv_payload)

    _fin, prov = sp.fetch_ticker("TST", "2026-09-12", with_provenance=True)
    assert prov["revenue"]["observed_kind"] == "unstated"
    assert prov["revenue"]["basis_conflict"] is False


@pytest.mark.unit
@pytest.mark.parametrize(
    ("token", "kind"),
    [
        ("2025/FY", "annual"),
        ("Income Statement (FY 2025)", "annual"),
        ("FY2026 annual", "annual"),
        ("2026/Q2", "quarterly"),
        ("2026-Q3", "quarterly"),
        ("Quarter ended 2026-07-31", "quarterly"),
        ("TTM 2026-07-31", "ttm"),
        ("trailing twelve months", "ttm"),
        ("2026-01-31", "unstated"),
        ("", "unstated"),
        (None, "unstated"),
    ],
)
def test_period_kind_classifies_vendor_labels(token, kind):
    assert sp._period_kind(token) == kind


@pytest.mark.unit
def test_basis_conflict_only_fires_on_a_contradicting_kind():
    assert sp._basis_conflict("annual", "quarterly") is True
    assert sp._basis_conflict("annual", "ttm") is True
    assert sp._basis_conflict("quarterly", "annual") is True
    assert sp._basis_conflict("quarterly", "ttm") is True
    assert sp._basis_conflict("annual", "annual") is False
    assert sp._basis_conflict("annual", "unstated") is False
    # The fundamentals pull asks for no basis, so it can never conflict.
    assert sp._basis_conflict("info", "quarterly") is False


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


# --- Multi-year canonical series -------------------------------------------
#
# The Mohanram G-Score's G4/G5 legs read ``roa_series`` / ``revenue_series`` and
# the earnings-quality tool reads the cash-flow series for Dechow-Dichev - and
# NONE of those keys had a producer (2026-09-17 factor-model inventory), so
# ``var_roa`` / ``var_sales_growth`` were structurally absent and ``dd_aq``
# could not fire. ``annual_series`` is that producer.

_MOOMOO_MULTIYEAR = (
    "### Income Statement (2025/FY)\n"
    "| Item | 2025/FY | YoY |\n| --- | --- | --- |\n"
    "| Total Operating Revenue | 281,724,000,000 | 17.4% |\n"
    "| Net Income to Common | 101,832,000,000 | 15.7% |\n"
    "### Balance Sheet (2025/FY)\n"
    "| Item | 2025/FY |\n| --- | --- |\n"
    "| Total Assets | 619,003,000,000 |\n"
    "### Income Statement (2024/FY)\n"
    "| Item | 2024/FY | YoY |\n| --- | --- | --- |\n"
    "| Total Operating Revenue | 240,000,000,000 | 20.0% |\n"
    "| Net Income to Common | 88,000,000,000 | 22.2% |\n"
    "### Balance Sheet (2024/FY)\n"
    "| Item | 2024/FY |\n| --- | --- |\n"
    "| Total Assets | 512,163,000,000 |\n"
    "### Income Statement (2023/FY)\n"
    "| Item | 2023/FY | YoY |\n| --- | --- | --- |\n"
    "| Total Operating Revenue | 200,000,000,000 | 7.0% |\n"
    "| Net Income to Common | 72,000,000,000 | 12.0% |\n"
    "### Balance Sheet (2023/FY)\n"
    "| Item | 2023/FY |\n| --- | --- |\n"
    "| Total Assets | 411,976,000,000 |\n"
)

_INCOME_CSV = (
    ",2025-09-30,2024-09-30,2023-09-30\n"
    "Total Revenue,281724000000,240000000000,200000000000\n"
    "Net Income,101832000000,88000000000,72000000000\n"
)

_BALANCE_CSV = (
    ",2025-09-30,2024-09-30,2023-09-30\n"
    "Total Assets,619003000000,512163000000,411976000000\n"
)


@pytest.mark.unit
def test_annual_series_merges_a_moomoo_payload_by_fiscal_year():
    """A moomoo ``get_fundamentals`` payload carries one table per STATEMENT
    per period. Two tables for one year must merge into ONE period, not two
    half-empty ones - otherwise the revenue (income table) and the assets
    (balance table) never coexist in a year and no series can form."""
    got = sp.annual_series([_MOOMOO_MULTIYEAR])
    assert got["revenue_series"]["values"] == pytest.approx(
        [200.0e9, 240.0e9, 281.724e9]
    )
    assert got["revenue_series"]["years"] == [2023, 2024, 2025]
    assert got["revenue_series"]["periods"] == ["2023/FY", "2024/FY", "2025/FY"]
    assert got["net_income_series"]["values"][-1] == pytest.approx(101.832e9)
    assert got["total_assets_series"]["values"] == pytest.approx(
        [411.976e9, 512.163e9, 619.003e9]
    )
    # ROA on BEGINNING-of-year assets (the convention growth_metrics uses for
    # the level), so the oldest year drops out: 2024 NI / 2023 TA.
    assert got["roa_series"]["years"] == [2024, 2025]
    assert got["roa_series"]["values"][0] == pytest.approx(88.0e9 / 411.976e9)
    assert got["roa_series"]["values"][1] == pytest.approx(101.832e9 / 512.163e9)


@pytest.mark.unit
def test_annual_series_joins_income_and_balance_across_payloads():
    """The yfinance path pulls the income and balance statements as SEPARATE
    payloads, and the level ROA already joins them (``enrich_screen_ratios``);
    the series does the same, aligned by fiscal year rather than by position."""
    got = sp.annual_series([_INCOME_CSV, _BALANCE_CSV])
    assert got["revenue_series"]["values"] == pytest.approx(
        [200.0e9, 240.0e9, 281.724e9]
    )
    assert got["total_assets_series"]["values"] == pytest.approx(
        [411.976e9, 512.163e9, 619.003e9]
    )
    assert got["roa_series"]["years"] == [2024, 2025]
    assert got["roa_series"]["values"][1] == pytest.approx(101.832e9 / 512.163e9)


@pytest.mark.unit
def test_annual_series_skips_a_year_with_no_prior_balance_sheet():
    """A gap in the balance series is SKIPPED, never closed by re-indexing: the
    ROA of 2025 divides by the 2024 balance sheet, and a missing 2024 means no
    2025 ROA rather than a division by the 2023 figure."""
    balance_missing_2024 = (
        ",2025-09-30,2023-09-30\n"
        "Total Assets,619003000000,411976000000\n"
    )
    got = sp.annual_series([_INCOME_CSV, balance_missing_2024])
    assert "roa_series" not in got  # only 2025 could be computed -> < 2 points
    assert got["total_assets_series"]["years"] == [2023, 2025]


@pytest.mark.unit
def test_annual_series_omits_an_incomplete_key():
    """A key missing in ANY period is omitted, never zero-filled."""
    holey = (
        ",2025-09-30,2024-09-30,2023-09-30\n"
        "Total Revenue,281724000000,240000000000,200000000000\n"
        "Net Income,,88000000000,72000000000\n"
    )
    got = sp.annual_series([holey])
    assert "revenue_series" in got
    assert "net_income_series" not in got


@pytest.mark.unit
def test_annual_series_needs_two_periods_and_a_payload():
    one_year = ",2025-09-30\nTotal Revenue,281724000000\nNet Income,101832000000\n"
    assert sp.annual_series([one_year]) == {}
    assert sp.annual_series([]) == {}
    assert sp.annual_series(["NO_DATA_AVAILABLE: x"]) == {}
    assert sp.annual_series(["not a statement at all"]) == {}


@pytest.mark.unit
def test_fetch_ticker_attaches_the_series_with_provenance(monkeypatch):
    """The series reaches the canonical dict the score readers consume, and its
    provenance states that it is derived and over which periods."""

    def _fake(method, *args, **kwargs):
        if method == "get_income_statement":
            return _INCOME_CSV
        if method == "get_balance_sheet":
            return _BALANCE_CSV
        raise RuntimeError("no vendor for " + method)

    monkeypatch.setattr(sp, "route_to_vendor", _fake)
    fin, prov = sp.fetch_ticker("TST", "2026-09-12", with_provenance=True)
    assert fin["revenue_series"] == pytest.approx([200.0e9, 240.0e9, 281.724e9])
    assert fin["roa_series"] == pytest.approx(
        [88.0e9 / 411.976e9, 101.832e9 / 512.163e9]
    )
    entry = prov["revenue_series"]
    assert entry["source"] == "derived"
    assert "3 period(s)" in entry["basis"]
    assert entry["period"] == "2023-09-30 .. 2025-09-30"
    # A bare date header states no kind, so no conflict is claimed on layout.
    assert entry["observed_kind"] == "unstated"
    assert entry["basis_conflict"] is False


@pytest.mark.unit
def test_fetch_ticker_series_light_up_the_g_score_legs(monkeypatch):
    """The producer's whole point: the G-Score's variance legs stop reporting
    "series unavailable". Six periods, so G4/G5 are computable when the peer
    medians are supplied."""
    six_year_income = (
        ",2025-09-30,2024-09-30,2023-09-30,2022-09-30,2021-09-30,2020-09-30\n"
        "Total Revenue,281724000000,240000000000,200000000000,"
        "180000000000,170000000000,160000000000\n"
        "Net Income,101832000000,88000000000,72000000000,"
        "60000000000,55000000000,50000000000\n"
    )
    six_year_balance = (
        ",2025-09-30,2024-09-30,2023-09-30,2022-09-30,2021-09-30,2020-09-30\n"
        "Total Assets,619003000000,512163000000,411976000000,"
        "380000000000,350000000000,320000000000\n"
    )

    def _fake(method, *args, **kwargs):
        if method == "get_income_statement":
            return six_year_income
        if method == "get_balance_sheet":
            return six_year_balance
        raise RuntimeError("no vendor for " + method)

    monkeypatch.setattr(sp, "route_to_vendor", _fake)
    fin = sp.fetch_ticker("TST", "2026-09-12")

    from tradingagents.dataflows.quantitative_scores import growth_metrics, growth_score

    g = growth_metrics(fin)
    assert g["roa_series_n"] == 5  # six assets years -> five beginning-of-year ROAs
    assert g["revenue_series_n"] == 6
    assert g["var_roa"] is not None and g["var_sales_growth"] is not None

    read = growth_score(
        fin,
        medians={
            "var_roa": {"median": 0.01, "n": 9},
            "var_sales_growth": {"median": 0.01, "n": 9},
        },
    )
    assert isinstance(read["signals"]["g4"], bool)
    assert isinstance(read["signals"]["g5"], bool)
    assert not [d for d in read["deviations"] if "series unavailable" in d]


# ---------------------------------------------------------------------------
# P0-1: the SEC XBRL 10-K history as a deeper annual series
# ---------------------------------------------------------------------------

def _sec_rows(years, value_of):
    """10-K FY rows for the given fiscal years (flow rows span ~a full year)."""
    out = []
    for y in years:
        out.append({
            "end": f"{y}-06-30",
            "start": f"{y - 1}-07-01",
            "val": value_of(y),
            "form": "10-K",
            "fp": "FY",
        })
    return out


def _sec_facts(tags: dict) -> dict:
    return {"facts": {"us-gaap": {t: {"units": {"USD": rows}} for t, rows in tags.items()}}}


def _patch_sec(monkeypatch, facts: dict, cik: str | None = "1234"):
    from tradingagents.dataflows import sec_edgar

    monkeypatch.setattr(sec_edgar, "_json_get", lambda url, *a, **k: facts)
    monkeypatch.setattr(sec_edgar, "_cik_for", lambda ticker: cik)


_YEARS = (2021, 2022, 2023, 2024, 2025, 2026)


@pytest.mark.unit
def test_sec_annual_series_maps_labels_and_derives_the_untagged_rows(monkeypatch):
    """EBITDA and FCF have no us-gaap tag, so they are DERIVED here and labelled
    derived; the tagged rows keep their own keys, and the ROA series is derived
    on beginning-of-year assets exactly as the vendor path derives it."""
    _patch_sec(monkeypatch, _sec_facts({
        "NetIncomeLoss": _sec_rows(_YEARS, lambda y: (y - 2020) * 10e9),
        "Assets": _sec_rows(_YEARS, lambda y: (y - 2020) * 100e9),
        "OperatingIncomeLoss": _sec_rows(_YEARS, lambda y: (y - 2020) * 20e9),
        "DepreciationDepletionAndAmortization": _sec_rows(_YEARS, lambda y: 5e9),
        "NetCashProvidedByUsedInOperatingActivities": _sec_rows(_YEARS, lambda y: (y - 2020) * 15e9),
        "PaymentsToAcquirePropertyPlantAndEquipment": _sec_rows(_YEARS, lambda y: 2e9),
    }))
    got = sp.sec_annual_series("TST")

    assert got["net_income_series"]["values"] == [v * 10e9 for v in range(1, 7)]
    assert got["net_income_series"]["years"] == list(_YEARS)
    assert got["net_income_series"]["periods"][0] == "2021-06-30"
    # 2022..2026 have a prior-year balance sheet; 2021 has none.
    assert len(got["roa_series"]["values"]) == 5
    assert got["roa_series"]["years"] == list(_YEARS[1:])
    assert got["roa_series"]["values"][0] == pytest.approx(20e9 / 100e9)
    # Derived, and labelled as such: EBITDA = operating income + D&A.
    assert got["ebitda_series"]["derived"] is True
    assert got["ebitda_series"]["values"][0] == pytest.approx(20e9 + 5e9)
    # FCF = OCF - capex (capex is filed positive).
    assert got["fcf_series"]["derived"] is True
    assert got["fcf_series"]["values"][0] == pytest.approx(15e9 - 2e9)


@pytest.mark.unit
def test_sec_annual_series_is_empty_when_edgar_has_no_record(monkeypatch):
    """A non-US ticker has no CIK: the series is OPTIONAL depth and must return
    an empty dict rather than raising into a caller that never asked for it."""
    _patch_sec(monkeypatch, {}, cik=None)
    assert sp.sec_annual_series("0700.HK") == {}


@pytest.mark.unit
def test_sec_annual_series_keeps_only_the_longest_unbroken_run(monkeypatch):
    """A tag that skips a year contributes its longest CONSECUTIVE stretch: the
    readers index these arrays by position, so a hole would misalign them."""
    holey = _sec_rows([y for y in _YEARS if y != 2024], lambda y: float(y))
    _patch_sec(monkeypatch, _sec_facts({"NetIncomeLoss": holey}))
    got = sp.sec_annual_series("TST")
    assert got["net_income_series"]["years"] == [2021, 2022, 2023]


@pytest.mark.unit
def test_fetch_ticker_asks_edgar_only_when_the_caller_asks_for_the_depth(monkeypatch):
    """The SEC merge is OPT-IN: it costs a request and carries a different basis
    (as-reported USD), so the default path must stay exactly the vendor chain it
    is today - and when asked, the longer series wins PER KEY and names its
    source."""
    annual_income = (
        ",2026-06-30,2025-06-30\n"
        "Total Revenue,215940000000.0,130500000000.0\n"
        "Net Income,120070000000.0,72880000000.0\n"
    )

    def _fake_vendor(method, *args, **kwargs):
        if method == "get_income_statement":
            return annual_income
        raise RuntimeError("no vendor for " + method)

    monkeypatch.setattr(sp, "route_to_vendor", _fake_vendor)
    calls: list[str] = []

    def _fake_sec(ticker, years=15):
        calls.append(ticker)
        return {
            "net_income_series": {
                "values": [float(v) for v in range(1, 7)],
                "years": list(_YEARS),
                "periods": [f"{y}-06-30" for y in _YEARS],
            }
        }

    monkeypatch.setattr(sp, "sec_annual_series", _fake_sec)

    plain = sp.fetch_ticker("TST", "2026-09-12")
    assert calls == []  # the default path never touches EDGAR
    assert len(plain["net_income_series"]) == 2

    fin, prov = sp.fetch_ticker("TST", "2026-09-12", with_provenance=True, with_sec_series=True)
    assert calls == ["TST"]
    assert len(fin["net_income_series"]) == 6  # the longer series won
    assert prov["net_income_series"]["source"] == "sec_xbrl"
    assert prov["net_income_series"]["observed_kind"] == "annual"
