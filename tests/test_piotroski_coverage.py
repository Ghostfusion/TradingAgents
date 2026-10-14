"""A partial Piotroski sum must not read as a measurement.

``piotroski_f_score`` sums nine binary signals and scores an unmeasurable one as
0, so a thin vendor payload reads as weakness. GMED 2026-10-14 published
``Piotroski F: 3.00`` and ``trap_risk: MEDIUM`` on the strength of it while the
prior-period legs were missing; an hour later the same ticker read 8.00 at 8 of
9 signals computable. The paper's bands (0-2 weak / 8-9 strong) are defined over
all nine signals, so the F leg may only fire on a complete read.
"""

from tradingagents.agents.utils.analysis_tools import screen_value_line
from tradingagents.strategies.normalized import trap_verdict


def test_under_covered_f_score_cannot_raise_trap_risk():
    out = trap_verdict(f_score=3, f_coverage=3)
    assert out["level"] == "LOW"
    assert out["evidence"] == []
    assert "3 of 9 signals computable" in out["f_score_excluded"]


def test_fully_covered_low_f_score_still_fires():
    out = trap_verdict(f_score=3, f_coverage=9)
    assert out["level"] == "MEDIUM"
    assert any("f_score=3" in item for item in out["evidence"])
    assert "f_score_excluded" not in out


def test_another_leg_still_raises_the_level_with_the_f_leg_excluded():
    out = trap_verdict(f_score=3, f_coverage=3, m_score=-1.0)  # Beneish M > -1.78
    assert out["level"] == "MEDIUM"
    assert out["f_score_excluded"]
    assert any("beneish_m" in item for item in out["evidence"])


def test_no_coverage_read_keeps_the_legacy_behaviour():
    assert trap_verdict(f_score=3)["level"] == "MEDIUM"


def test_the_printed_line_names_the_coverage():
    line = screen_value_line("f_score", 3.0, None, coverage=3, withheld=["f_eq", "f_droa"])
    assert "PARTIAL: 3 of 9 signals" in line
    assert "f_eq" in line
    assert "not evidence of weakness" in line


def test_a_complete_read_prints_plainly():
    assert screen_value_line("f_score", 8.0, None, coverage=9) == "  Piotroski F: 8.00"
    assert screen_value_line("f_score", 8.0, None) == "  Piotroski F: 8.00"


def test_screen_ticker_publishes_the_coverage_and_excludes_the_leg():
    """The row the analyst verdict renders carries the coverage, always."""
    from tradingagents.dataflows.statement_parsing import screen_ticker

    fin = {
        "net_income": {"current": 100.0, "prior": 50.0},
        "total_assets": {"current": 1000.0, "prior": 900.0},
        "operating_cashflow": {"current": 120.0},
        "total_debt": {"current": 10.0, "prior": 20.0},
        "current_assets": {"current": 400.0, "prior": 300.0},
        "current_liabilities": {"current": 200.0, "prior": 200.0},
        "revenue": {"current": 800.0, "prior": 700.0},
        "cost_of_revenue": {"current": 500.0, "prior": 400.0},
        "total_equity": {"current": 600.0},
        "total_liabilities": {"current": 400.0},
        "market_cap": {"current": 5000.0},
    }
    row = screen_ticker("AAA", fin)
    assert row["f_score_n"] is not None and 0 <= row["f_score_n"] <= 9
    assert isinstance(row["f_score_withheld"], list)
    if row["f_score_n"] < 9:
        # Under-covered: the leg is excluded and the reason is on the row.
        assert row["trap_excluded"] and "computable" in row["trap_excluded"]
    else:
        assert row["trap_excluded"] is None
