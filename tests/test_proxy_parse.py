"""UNIV-GOV - proxy statement table extraction, against a fixture (no network)."""

import pytest

from tradingagents.dataflows.proxy import (
    extract_tables,
    fetch_proxy_html,
    governance_tables,
)

pytestmark = pytest.mark.timeout(600)

FIXTURE = """
<html><body>
<h2>Executive Compensation</h2>
<p>The following table, our Summary Compensation Table, sets forth the compensation of our named executive officers.</p>
<table>
  <tr><th>Name</th><th>Salary</th><th>Bonus</th></tr>
  <tr><td>Jane Doe</td><td>$1,000,000</td><td>$2,000,000</td></tr>
  <tr><td>John Roe</td><td>$900,000</td><td>$1,100,000</td></tr>
</table>
<h3>Director Compensation</h3>
<table>
  <tr><th>Name</th><th>Fees Earned</th></tr>
  <tr><td>Ann Lee</td><td>$250,000</td></tr>
</table>
<h3>Selected Financial Data</h3>
<table>
  <tr><th>Year</th><th>Revenue</th></tr>
  <tr><td>2025</td><td>$10</td></tr>
</table>
</body></html>
"""


def test_every_table_is_captured():
    assert len(extract_tables(FIXTURE)) == 3


def test_rows_and_columns_are_counted():
    first = extract_tables(FIXTURE)[0]
    assert first["n_rows"] == 3
    assert first["n_cols"] == 3


def test_cells_are_cleaned_text():
    first = extract_tables(FIXTURE)[0]
    assert first["rows"][1] == ["Jane Doe", "$1,000,000", "$2,000,000"]


def test_a_table_carries_the_heading_that_names_it():
    headings = [t["heading"] for t in extract_tables(FIXTURE)]
    assert "Director Compensation" in headings[1]
    assert "Selected Financial Data" in headings[2]


def test_the_summary_compensation_caption_is_found():
    """A real proxy names this table in prose, not in a heading tag."""
    first = extract_tables(FIXTURE)[0]
    assert "Summary Compensation Table" in first["heading"]


def test_only_governance_tables_are_kept():
    kept = governance_tables(FIXTURE)
    assert len(kept) == 2
    headings = " ".join(t["heading"] for t in kept)
    assert "Director Compensation" in headings
    assert "Selected Financial Data" not in headings


def test_an_unrelated_table_is_never_claimed_as_governance():
    for table in governance_tables(FIXTURE):
        assert "Financial Data" not in table["heading"]


def test_unparseable_input_is_empty_not_an_error():
    assert extract_tables("") == []


def test_a_table_with_no_heading_is_not_claimed():
    orphan = "<html><body><table><tr><td>a</td></tr></table></body></html>"
    assert extract_tables(orphan)[0]["n_rows"] == 1
    assert governance_tables(orphan) == []


def test_nested_markup_inside_cells_is_flattened():
    html = "<table><tr><td><b>Ann</b> Lee</td></tr></table>"
    assert extract_tables(html)[0]["rows"][0] == ["Ann Lee"]


def test_no_cik_means_no_proxy_and_no_exception():
    url, html = fetch_proxy_html("NOT-A-REAL-TICKER-XYZ")
    assert url == "" and html == ""
