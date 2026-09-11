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
