"""P0-10: ``_match_row`` alias ordering / exclusion regressions.

The canonical line-item matcher resolves a row by substring-matching alias
tables in order. Three alias tables used to hand back the wrong line from a
payload that has no ambiguity at all:

- ``revenue`` fell through to its ``operating income`` last-resort alias even
  when an explicit ``Sales`` row was present (``sales`` was listed last);
- ``operating_income`` matched the ``EBITDA`` row because ``'ebit'`` is a
  substring of ``'ebitda'``;
- ``total_liabilities`` matched the combined ``Total Liabilities And Equity``
  balance line, inflating liabilities by shareholders' equity.

Every case below is synthetic-row based and asserts the returned
``(label, value)`` pair (or the canonical dict ``_canonicalize`` derives from a
vendor-style text payload) - never a private structure.
"""

from __future__ import annotations

import pytest

from tradingagents.dataflows.statement_parsing import _canonicalize, _match_row

# ---------------------------------------------------------------------------
# revenue: an explicit Sales row must beat the operating-income fallback
# ---------------------------------------------------------------------------


def test_revenue_prefers_sales_over_operating_income():
    rows = {"Operating Income": 100.0, "Sales": 250.0}

    assert _match_row(rows, "revenue") == ("Sales", 250.0)


def test_revenue_prefers_total_revenue_over_sales():
    rows = {"Sales": 240.0, "Total Revenue": 250.0, "Operating Income": 100.0}

    assert _match_row(rows, "revenue") == ("Total Revenue", 250.0)


def test_revenue_keeps_operating_income_as_documented_last_resort():
    # No revenue/sales row at all: the last-resort alias is all that is left,
    # and reporting it is preferable to returning nothing.
    assert _match_row({"Operating Income": 100.0}, "revenue") == ("Operating Income", 100.0)


def test_canonicalize_reports_sales_as_revenue():
    payload = "Operating Income : 100\nSales : 250\n"

    assert _canonicalize(payload)["revenue"] == 250.0


# ---------------------------------------------------------------------------
# operating_income: EBITDA is not EBIT
# ---------------------------------------------------------------------------


def test_operating_income_ignores_ebitda_only_payload():
    assert _match_row({"EBITDA": 500.0}, "operating_income") is None


def test_operating_income_keeps_real_row_when_ebitda_is_present():
    rows = {"EBITDA": 500.0, "Operating Income": 120.0}

    assert _match_row(rows, "operating_income") == ("Operating Income", 120.0)


def test_operating_income_still_matches_a_real_ebit_row():
    # The exclusion is scoped to the EBITDA label, not the 'ebit' alias.
    assert _match_row({"EBIT": 90.0}, "operating_income") == ("EBIT", 90.0)


def test_canonicalize_does_not_report_ebitda_as_operating_income():
    payload = "EBITDA : 500\n"

    assert "operating_income" not in _canonicalize(payload)


# ---------------------------------------------------------------------------
# total_liabilities / total_debt: the combined equity line is not liabilities
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "combined_label",
    ["Total Liabilities And Equity", "Total Liabilities & Equity",
     "Total Liabilities And Stockholders Equity"],
)
def test_total_liabilities_ignores_combined_equity_line(combined_label):
    assert _match_row({combined_label: 500.0}, "total_liabilities") is None


def test_total_liabilities_keeps_standalone_row_over_combined_line():
    rows = {"Total Liabilities And Equity": 500.0, "Total Liabilities": 300.0}

    assert _match_row(rows, "total_liabilities") == ("Total Liabilities", 300.0)


def test_total_debt_ignores_combined_equity_line():
    rows = {"Total Liabilities And Stockholders Equity": 500.0, "Total Liabilities": 300.0}

    # total_debt's documented last-resort alias is 'total liabilities'; the
    # equity-carrying combined line must not stand in for it.
    assert _match_row(rows, "total_debt") == ("Total Liabilities", 300.0)


def test_canonicalize_omits_liabilities_for_combined_line_only():
    payload = "Total Liabilities And Equity : 500\nTotal Assets : 900\n"

    canonical = _canonicalize(payload)
    assert "total_liabilities" not in canonical
    assert canonical["total_assets"] == 900.0


def test_alpha_vantage_overview_keeps_single_level_numeric_fields():
    """AV's OVERVIEW payload is flat camelCase; its numeric fields must survive.

    Dropping them left market_cap / shares / beta unparsed whenever Alpha
    Vantage served (EV, earnings yield, Altman and the net-net test all degrade
    to n/a), and the raw camelCase labels could not match the space-separated
    aliases even when they were kept.
    """
    import json

    from tradingagents.dataflows.statement_parsing import (
        _canonicalize,
        _parse_json_statements,
    )

    payload = json.dumps({
        "Symbol": "AAPL",
        "Sector": "TECHNOLOGY",
        "MarketCapitalization": "3000000000000",
        "SharesOutstanding": "15000000000",
        "Beta": "1.24",
        "DividendYield": "0.0055",
        "fiscalDateEnding": "2026-06-30",
        "reportedCurrency": "USD",
        "annualReports": [{"fiscalDateEnding": "2026-06-30", "totalRevenue": "400000000000",
                           "netIncome": "100000000000"}],
    })
    rows = _parse_json_statements(payload)

    # The single-level numeric fields are no longer dropped.
    assert rows["Market Capitalization"] == 3000000000000.0
    assert rows["Shares Outstanding"] == 15000000000.0
    assert rows["Beta"] == 1.24

    canon = _canonicalize(payload)
    assert canon.get("market_cap") == 3000000000000.0      # matched via the camelCase alias
    assert canon.get("shares") == 15000000000.0            # needed the camel-case split
    assert canon.get("beta") == 1.24
    assert canon.get("revenue") == 400000000000.0          # snake_case report key


# ---------------------------------------------------------------------------
# A negated row is not the row: "non current" is not current, "other
# non-operating income" is not operating income
# ---------------------------------------------------------------------------

# yfinance's balance-sheet row order (Ticker.balance_sheet, 2026-09): the
# non-current aggregates precede the current ones, and the current rows carry no
# "Total" prefix, so the ``current assets`` fallback alias used to land on the
# non-current line. MSFT 2026-09-16: current_assets 550.67bn (= total
# NON-current) against the statement's own 207.71bn, giving the balance-sheet
# health tool a 3.74 current ratio against ratios' 1.23 and a 403.5bn working
# capital against 38.9bn (Altman Z, Ohlson and Zmijewski all read it).
_YF_BALANCE_ROWS = {
    "Total Liabilities Net Minority Interest": 315989000000.0,
    "Total Non Current Liabilities Net Minority Interest": 147164000000.0,
    "Long Term Debt": 31070000000.0,
    "Current Liabilities": 168825000000.0,
    "Total Assets": 758376000000.0,
    "Total Non Current Assets": 550666000000.0,
    "Net PPE": 337253000000.0,
    "Current Assets": 207710000000.0,
    "Cash And Cash Equivalents": 20935000000.0,
    "Retained Earnings": 328265000000.0,
    "Gains Losses Not Affecting Retained Earnings": -3284000000.0,
    "Accumulated Depreciation": -118691000000.0,
    "Total Debt": 56826000000.0,
}


def test_current_assets_prefers_the_current_row_over_the_non_current_one():
    assert _match_row(_YF_BALANCE_ROWS, "current_assets") == ("Current Assets", 207710000000.0)


def test_current_liabilities_prefers_the_current_row_over_the_non_current_one():
    assert (
        _match_row(_YF_BALANCE_ROWS, "current_liabilities")
        == ("Current Liabilities", 168825000000.0)
    )


def test_retained_earnings_ignores_the_aoci_row():
    assert (
        _match_row(_YF_BALANCE_ROWS, "retained_earnings")
        == ("Retained Earnings", 328265000000.0)
    )


def test_depreciation_of_a_balance_sheet_is_not_the_accumulated_contra_row():
    # A balance sheet states no period depreciation; the accumulated contra
    # account (-118.69bn) must not stand in for the expense.
    assert _match_row(_YF_BALANCE_ROWS, "depreciation") is None


def test_revenue_ignores_a_deferred_revenue_liability():
    assert _match_row({"Non Current Deferred Revenue": 2747000000.0}, "revenue") is None


def test_canonicalize_reads_the_current_rows_of_a_yfinance_balance_sheet():
    """The observable effect: the canonical items, not the matcher internals."""
    payload = ",2026-06-30,2025-06-30\n" + "".join(
        f"{label},{value},0\n" for label, value in _YF_BALANCE_ROWS.items()
    )
    canonical = _canonicalize(payload)

    assert canonical["current_assets"] == 207710000000.0
    assert canonical["current_liabilities"] == 168825000000.0
    assert canonical["retained_earnings"] == 328265000000.0


def test_operating_income_ignores_other_non_operating_income():
    # moomoo's annual income statement labels the real row "Operating Profit";
    # "Other Non-Operating Income (Expenses)" (4.72bn on MSFT) matched the
    # ``operating income`` alias first and produced EV/EBIT 779 against a true
    # 23.7 and an 0.13% earnings yield against 4.22%.
    rows = {
        "Other Income (Expense)": 10450000000.0,
        "Other Non-Operating Income (Expenses)": 4720000000.0,
        "Operating Profit": 155240000000.0,
        "Pretax Profit": 165930000000.0,
    }

    assert _match_row(rows, "operating_income") == ("Operating Profit", 155240000000.0)


def test_a_negated_only_row_still_matches_on_the_retry():
    # Some items are only ever reported negated: moomoo's income statement has
    # no plain "Interest Expense" row for MSFT, so the negated label is the
    # right answer once the plain scan finds nothing.
    rows = {"Non-Operating Interest Income": 3300000000.0, "Non-Operating Interest Expense": 3050000000.0}

    assert _match_row(rows, "interest_expense") == ("Non-Operating Interest Expense", 3050000000.0)


def test_canonicalize_reads_operating_profit_when_moomoo_reports_it_so():
    payload = (
        "### 2026/FY\n"
        "| Item | Value | YoY | QoQ |\n"
        "| --- | --- | --- | --- |\n"
        "| Other Non-Operating Income (Expenses) | $4.72B | 199.94% | -- |\n"
        "| Operating Profit | $155.24B | 20.78% | -- |\n"
    )

    canonical = _canonicalize(payload)

    # A single-period payload yields a flat value (the prior dict form needs a
    # second period table).
    assert canonical["operating_income"] == 155240000000.0


# ---------------------------------------------------------------------------
# sector: an industry-GROUP row must never fill the sector key
# ---------------------------------------------------------------------------


def test_no_sector_alias_can_be_satisfied_by_an_industry_group_row():
    """``fin["sector"]`` (statement_parsing.py:1555) selects the Altman variant
    and feeds the Piotroski basis, so an industry-group value landing there is a
    silently wrong model choice - ``altman_variant_for`` resolves it through
    ``sector_group_of`` and a stray financial group WITHHOLDS the variant for a
    non-financial company.

    The removed alias was the unspaced ``industrygroup``. ``_norm`` replaces
    non-alphanumerics with a SPACE, so the spaced vendor label "Industry Group"
    never matched it; an UNSEPARATED label ("IndustryGroup") did. Both must miss.
    """
    from tradingagents.dataflows.statement_parsing import _ROW_ALIASES, _norm

    aliases = _ROW_ALIASES["sector"]
    assert aliases == ["sector"]
    for label in ("Industry Group", "IndustryGroup", "industry group"):
        assert _norm(label) not in aliases, label


def test_an_industry_group_row_does_not_match_the_sector_key():
    from tradingagents.dataflows.statement_parsing import _match_row

    # The spaced form never matched: the alias had no separator to strip.
    assert _match_row({"Industry Group": 42.0}, "sector") is None
    # The unseparated form DID match before the alias was removed.
    assert _match_row({"IndustryGroup": 42.0}, "sector") is None
    # The sector row itself still fills the key.
    assert _match_row({"Sector": "Technology"}, "sector") == ("Sector", "Technology")
