"""The S&P 500 constituent parser: every Symbol/Security source shape.

The page's Symbol column renders `{{NyseSymbol|MMM}}` or `{{NasdaqSymbol|ADBE}}`,
its Security cell is sometimes a piped wikilink (`[[AMD|Advanced Micro Devices]]`),
and two tickers carry an HTML guard comment. Matching only the first template
silently dropped the Nasdaq half of the index - AAPL, MSFT, NVDA among them - so
the sector screen and the market-breadth panel were built on 317 names instead of
~502 (measured live 2026-09-27: 502 template occurrences, 317 parsed before, 501
after).
"""

from __future__ import annotations

import pytest

from tradingagents.dataflows import sp500_universe as su

pytestmark = pytest.mark.timeout(600)


# The constituent table in the three shapes the live page uses (simple cells, a
# piped wikilink, a guard comment, and cells split across lines), plus the
# "selected changes" table whose rows also carry symbol templates.
WIKITEXT = """
{| class="wikitable sortable"
__omp_shell("Symbol !! Security !! GICS Sector !! GICS Sub-Industry")
|-
| {{NyseSymbol|MMM}} || 3M || Industrials || Industrial Conglomerates
|-
| {{NasdaqSymbol|AAPL}} || Apple Inc. || Information Technology || Technology Hardware
|-
| {{NasdaqSymbol|AMD}} || [[AMD|Advanced Micro Devices]] || Information Technology || Semiconductors
|-
| {{NyseSymbol|BRK.B}} <!-- DO NOT CHANGE THIS TICKER TO BRK-B. IT IS NOT CORRECT AND WILL BE REVERTED. --> || [[Berkshire Hathaway|Berkshire Hathaway]] || Financials || Multi-Sector Holdings
|-
|| {{NyseSymbol|XOM}}
|| ExxonMobil
|| Energy
|| Integrated Oil & Gas
|}

{| class="wikitable"
__omp_shell("Date !! Added !! Removed !! Reason")
|-
| {{NyseSymbol|FOO}} || {{NasdaqSymbol|BAR}} || Example || Merger
|}
"""


def _flat() -> set[str]:
    rows, _ = su._parse_wikitext(WIKITEXT)
    return {t for names in rows.values() for t in names}


def test_both_exchange_templates_are_parsed():
    rows, bucketed = su._parse_wikitext(WIKITEXT)
    assert bucketed == 5
    assert rows["XLI"] == ["MMM"]
    assert rows["XLK"] == ["AAPL", "AMD"], "the Nasdaq rows are the class that was dropped"
    assert rows["XLF"] == ["BRK-B"]
    assert rows["XLE"] == ["XOM"]


def test_a_piped_wikilink_security_cell_still_yields_a_row():
    # `[^|]+` cannot span `[[AMD|Advanced Micro Devices]]` - 42 live rows failed
    # for this reason alone.
    assert "AMD" in _flat()


def test_a_guard_comment_after_the_ticker_still_yields_a_row():
    assert "BRK-B" in _flat()


def test_the_symbol_dot_maps_to_the_vendor_dash():
    flat = _flat()
    assert "BRK-B" in flat and "BRK.B" not in flat


def test_the_changes_table_is_not_a_constituent_row():
    """A row is three cells of the constituent shape, not just a symbol template.

    The "selected changes" table repeats both templates, so widening the pattern
    for the Nasdaq half must not also admit its added/removed rows.
    """
    flat = _flat()
    assert "FOO" not in flat and "BAR" not in flat


def test_an_unknown_sector_is_dropped_not_bucketed():
    rows, bucketed = su._parse_wikitext(
        "|| {{NasdaqSymbol|ZZZ}} || Zed || Unmapped Sector || X ||"
    )
    assert rows == {} and bucketed == 0
