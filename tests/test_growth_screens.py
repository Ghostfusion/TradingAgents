"""Phase-1 growth / sector / institutional screens - parsing + CLI gates."""

from contextlib import ExitStack, contextmanager
from unittest import mock

import pytest

import scripts.value_screener as vs
from tradingagents.dataflows import statement_parsing as _sp_parsing


@contextmanager
def _patched_router(route):
    """Patch the vendor router wherever this module reaches it.

    ``fetch_ticker`` now lives in ``statement_parsing`` (the installed-CLI
    contract), so patching only ``vs.route_to_vendor`` would leak live vendor
    calls; patch both bindings.
    """
    with ExitStack() as stack:
        stack.enter_context(mock.patch.object(vs, "route_to_vendor", side_effect=route))
        stack.enter_context(
            mock.patch.object(_sp_parsing, "route_to_vendor", side_effect=route)
        )
        yield



# Tests drive vs.main() end-to-end (benchmark closes, growth/ROE/revision
# gates) on live vendor data; 15-60s each under a slow network. Keep the
# no-hang guard but allow a generous per-test budget.
pytestmark = pytest.mark.timeout(600)

INCOME_MD = """## Income Statement — US.AAPL

### 2025 (FY 2025, currency: USD)
| Item | Value | YoY | QoQ |
| --- | --- | --- | --- |
| Total Revenue | $391.04B | 3.4% | -6.1% |
| Diluted EPS | 7.21 | 12.1% | -0.8% |
| Net Income | $93.74B | 3.0% | -- |
"""

BALANCE_MD = """## Balance Sheet — US.AAPL
| Item | Value | YoY | QoQ |
| --- | --- | --- | --- |
| Total Assets | $364.98B | -- | -- |
| Total Stockholder Equity | $66.23B | -- | -- |
"""


def _fund_route(method, *a, **k):
    if method in ("get_fundamentals", "get_income_statement", "get_balance_sheet"):
        payload = INCOME_MD + "\n" + (BALANCE_MD if method == "get_balance_sheet" else "")
        return payload
    if method == "get_institution_holdings":
        return (
            "| Period | Institutions | Shares held | % of float | Chg (pp) |\n"
            "| --- | --- | --- | --- | --- |\n"
            "| 2025-Q4 | 5123 | 8.42B | 71.2% | +0.8pp |\n"
            "| 2025-Q3 | 5100 | 8.30B | 70.4% | +1.2pp |\n"
        )
    return "NO_DATA_AVAILABLE: no usable data"


# ---------------------------------------------------------------------------
# Parser units
# ---------------------------------------------------------------------------


def test_markdown_yoy_parsing():
    canon = vs._canonicalize(INCOME_MD)
    assert canon["revenue"] == pytest.approx(391.04e9)
    assert canon["revenue_yoy"] == pytest.approx(0.034)
    assert canon["eps"] == pytest.approx(7.21)
    assert canon["eps_yoy"] == pytest.approx(0.121)
    assert canon["net_income"] == pytest.approx(93.74e9)


def test_balance_equity_and_roe():
    canon = vs._canonicalize(INCOME_MD + "\n" + BALANCE_MD)
    assert canon["total_equity"] == pytest.approx(66.23e9)
    row = vs.screen_ticker("AAPL", canon)
    assert row["roe"] == pytest.approx(round(93.74e9 / 66.23e9, 4))
    assert row["eps_yoy"] == pytest.approx(0.121)


def test_moomoo_markdown_with_header_routes_to_markdown_parser():
    # moomoo payloads start with a "## " header - must still parse.
    payload = INCOME_MD
    assert vs._canonicalize(payload)["revenue"] == pytest.approx(391.04e9)


def test_percent_fraction_edge_cases():
    assert vs._percent_fraction("3.4%") == pytest.approx(0.034)
    assert vs._percent_fraction("-5.2%") == pytest.approx(-0.052)
    assert vs._percent_fraction("--") is None
    assert vs._percent_fraction(None) is None


def test_inst_accumulation_parse():
    blob = _fund_route("get_institution_holdings", "AAPL")
    info = vs._inst_accumulation(blob)
    assert info["latest_pp"] == pytest.approx(0.8)
    assert info["two_q_pp"] == pytest.approx(2.0)
    assert info["accumulate"] is True
    assert vs._inst_accumulation("NO_DATA_AVAILABLE: x") is None
    assert vs._inst_accumulation("") is None


# ---------------------------------------------------------------------------
# CLI gates (positional-ticker path, mocked vendor)
# ---------------------------------------------------------------------------


def test_growth_gates_pass_when_measured_ok(capsys):
    with _patched_router(_fund_route):
        vs.main(
            [
                "AAPL",
                "-d",
                "2026-01-02",
                "--min-mcap",
                "0",
                "--min-eps-yoy",
                "10",
                "--min-rev-yoy",
                "3",
                "--min-roe",
                "100",
            ]
        )
    out = capsys.readouterr().out
    assert "EpsYoY" in out and "RevYoY" in out and "ROE" in out
    assert "AAPL" in out


def test_growth_gate_eps_filters(capsys):
    with _patched_router(_fund_route):
        vs.main(["AAPL", "-d", "2026-01-02", "--min-eps-yoy", "30"])
    out = capsys.readouterr().out
    assert "AAPL" not in out  # measured below the gate -> row dropped


def test_growth_gate_roe_filters(capsys):
    with _patched_router(_fund_route):
        vs.main(["AAPL", "-d", "2026-01-02", "--min-roe", "150"])
    out = capsys.readouterr().out
    assert "AAPL" not in out


def test_max_mcap_gate(capsys):

    def cap_route(method, *a, **k):
        if method == "get_fundamentals":
            return "Market Cap: 50000000000\nSector: Technology\n"
        if method in ("get_income_statement", "get_balance_sheet"):
            return INCOME_MD + ("\n" + BALANCE_MD if method == "get_balance_sheet" else "")
        return "NO_DATA_AVAILABLE: no usable data"

    with _patched_router(cap_route):
        vs.main(["AAPL", "-d", "2026-01-02", "--max-mcap", "20000000000"])
    out = capsys.readouterr().out
    assert "AAPL" not in out  # 50B market cap above the 20B ceiling

    # Below the ceiling -> kept (no SystemExit).
    with (
        _patched_router(cap_route),
        mock.patch.object(vs, "print_watchlist", return_value=None),
    ):
        vs.main(["AAPL", "-d", "2026-01-02", "--max-mcap", "1000000000000"])


def test_inst_accum_gate_distribution_rejects(capsys):

    def dist_route(method, *a, **k):
        if method == "get_institution_holdings":
            return (
                "| 2025-Q4 | 5123 | 8.42B | 71.2% | -0.5pp |\n"
                "| 2025-Q3 | 5100 | 8.30B | 71.8% | +0.2pp |\n"
            )
        return _fund_route(method, *a, **k)

    with _patched_router(dist_route):
        vs.main(["AAPL", "-d", "2026-01-02", "--inst-accum"])
    out = capsys.readouterr().out
    assert "AAPL" not in out


def test_sector_rank_gate(capsys):

    fake_ranking = {
        "ranked": [
            {"etf": "XLK", "name": "Technology", "ret_3m": 0.12, "rank": 1},
            {"etf": "XLF", "name": "Financials", "ret_3m": 0.09, "rank": 2},
            {"etf": "XLE", "name": "Energy", "ret_3m": -0.02, "rank": 11},
        ],
        "top3_3m": ["XLK", "XLF"],
        "top3_1m": ["XLK", "XLF"],
    }

    with (
        _patched_router(_fund_route),
        mock.patch.object(vs, "_sector_ranking", return_value=fake_ranking),
        mock.patch.object(vs, "_fetch_sector_guarded", return_value="Technology"),
        mock.patch(
            "tradingagents.dataflows.finnhub.get_basic_financials_finnhub",
            return_value=None,
        ),
    ):
        vs.main(["AAPL", "-d", "2026-01-02", "--sector-rank"])
    out = capsys.readouterr().out
    assert "Sec" in out and "Rank" in out
    assert "T1" in out  # top-3 rank marker

    with (
        _patched_router(_fund_route),
        mock.patch.object(vs, "_sector_ranking", return_value=fake_ranking),
        mock.patch.object(vs, "_fetch_sector_guarded", return_value="Energy"),
        mock.patch(
            "tradingagents.dataflows.finnhub.get_basic_financials_finnhub",
            return_value=None,
        ),
    ):
        vs.main(["AAPL", "-d", "2026-01-02", "--sector-rank"])
    out = capsys.readouterr().out
    assert "AAPL" not in out  # measured not-top-3 sector -> dropped


def test_sector_rank_unknown_sector_keeps(capsys):
    with (
        _patched_router(_fund_route),
        mock.patch.object(
            vs, "_sector_ranking", return_value={"ranked": [], "top3_3m": [], "top3_1m": []}
        ),
        mock.patch.object(vs, "_fetch_sector_guarded", return_value=None),
    ):
        # unknown sector must not abort the run (data gap, not a fail)
        vs.main(["AAPL", "-d", "2026-01-02", "--sector-rank"])


def test_revision_gate(capsys):

    with (
        _patched_router(_fund_route),
        mock.patch.object(
            vs, "_fetch_revision_guarded", return_value={"up": 3, "down": 1, "net": 2}
        ),
    ):
        vs.main(["AAPL", "-d", "2026-01-02", "--revision"])
    out = capsys.readouterr().out
    assert "RevUp" in out

    with (
        _patched_router(_fund_route),
        mock.patch.object(
            vs, "_fetch_revision_guarded", return_value={"up": 1, "down": 3, "net": -2}
        ),
    ):
        vs.main(["AAPL", "-d", "2026-01-02", "--revision"])
    out = capsys.readouterr().out
    assert "AAPL" not in out  # negative revisions -> dropped


def test_revision_unknown_data_kept():
    with (
        _patched_router(_fund_route),
        mock.patch.object(vs, "_fetch_revision_guarded", return_value=None),
        mock.patch(
            "tradingagents.dataflows.finnhub.get_basic_financials_finnhub",
            return_value=None,
        ),
    ):
        vs.main(["AAPL", "-d", "2026-01-02", "--revision"])  # no SystemExit
