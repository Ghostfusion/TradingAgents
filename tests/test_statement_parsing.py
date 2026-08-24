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
def test_parse_csv_statements_takes_rightmost_column():
    rows = sp._parse_csv_statements(
        ",2025-09-30,2024-09-30,2023-09-30\n"
        "Free Cash Flow,95000000000,83000000000,69000000000\n"
    )
    assert rows["Free Cash Flow"] == 69_000_000_000.0  # rightmost numeric cell


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
