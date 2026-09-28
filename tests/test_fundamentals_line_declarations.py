"""FUND-17 / FUND-10: the R&D and deferred-revenue rows reach their keys.

Both rows were absent from the 106-factor table while their XBRL concepts rode
the ONE companyfacts payload the SEC leg already fetches - ``sec_edgar._TAG_MAP``
declares what ``annual_facts`` filters out of it, so an undeclared row is a row
the repo already downloaded and threw away. These tests pin the two behavioural
halves that were missing: the vendor-label reader resolves the rows, and the
growth reader consumes them.
"""

import pytest

from tradingagents.dataflows import quantitative_scores as qs, statement_parsing as sp

pytestmark = pytest.mark.timeout(600)


def test_research_and_development_resolves_from_a_vendor_label():
    rows = {"Research And Development": 35_562_000_000.0, "Total Revenue": 281_724_000_000.0}
    hit = sp._match_row(rows, "research_development")
    assert hit is not None
    assert hit[0] == "Research And Development"


def test_deferred_revenue_resolves_and_refuses_the_deferred_tax_rows():
    hit = sp._match_row({"Deferred Income Tax Liabilities": 1.0, "Deferred Revenue": 240.0},
                        "deferred_revenue")
    assert hit is not None
    assert hit[0] == "Deferred Revenue"
    # the deferred-INCOME-TAX row carries "deferred income", which the alias
    # list also matches; the exclude is the only thing keeping it out
    assert sp._match_row({"Deferred Income Tax Liabilities": 1.0}, "deferred_revenue") is None


def test_deferred_revenue_is_not_read_as_revenue():
    # a deferred balance is a LIABILITY, so the revenue alias must not take it
    assert sp._match_row({"Deferred Revenue": 240.0}, "revenue") is None


def test_growth_metrics_reads_the_rd_line_and_the_deferred_growth():
    gm = qs.growth_metrics({
        "revenue": 100.0,
        "research_development": 12.0,
        "deferred_revenue": {"current": 24.0, "prior": 20.0},
    })
    assert gm["rd_intensity"] == pytest.approx(0.12)
    assert gm["deferred_revenue_growth"] == pytest.approx(0.2)


def test_growth_metrics_omits_both_legs_rather_than_zeroing_them():
    gm = qs.growth_metrics({"revenue": 100.0})
    assert "rd_intensity" not in gm
    assert "deferred_revenue_growth" not in gm


def test_the_sec_label_is_declared_on_both_sides_of_the_contract():
    # ``_SEC_SERIES_KEYS``'s own comment: its labels are ``_TAG_MAP``'s, so the
    # two files must move together. A rename on one side alone drops the row.
    from tradingagents.dataflows import sec_edgar as se

    for label in ("Research and development", "Deferred revenue"):
        assert label in se._TAG_MAP
        assert label in sp._SEC_SERIES_KEYS
