"""X6 - the forward-rank study over the liquidity estimators that already exist.

Card: ``docs/paper_survey_26/implementation_plan_cross_section_and_allocation.md``
section 1, X6.

One producer each: the estimators are ``liquidity_risk.amihud_illiquidity`` /
``liquidity_risk.kyle_lambda`` and the statistic is ``signal_analysis.rank_ic``,
so the study adds neither and these tests never re-implement either. What they
defend is the one thing the study owns - the **window** its numbers are computed
against - plus the coverage contract: a symbol-month whose trade direction cannot
be determined reads ``unavailable`` (never a substituted value), and an empty
panel is reported rather than crashed on.

Offline and deterministic: the panel and the bars are synthetic, so no vendor
chain is touched.
"""

from __future__ import annotations

import pytest

from scripts.liquidity_forward_rank import (
    forward_rank_table,
    load_report_panel,
    render_text,
)
from tradingagents.strategies.liquidity_risk import amihud_illiquidity, kyle_lambda
from tradingagents.strategies.signal_analysis import rank_ic

MONTHS = ("2026-01", "2026-02", "2026-03")
TICKERS = [f"T{i:02d}" for i in range(12)]
MIN_OBS = 5
BASE = 100.0


def _month_dates(month: str) -> list[str]:
    return [f"{month}-{d:02d}" for d in (2, 4, 6, 10, 12, 16)]


def _bars_for_ticker(i: int) -> dict:
    """Six daily bars per month, built so the two return legs disagree in sign.

    Month ``2026-02``'s daily amplitude, the contemporaneous return
    (``2026-01`` -> ``2026-02``) and the forward return (``2026-02`` ->
    ``2026-03``) all rise with ``i``/fall with ``i`` respectively, so a
    ``kyle_lambda`` estimate at ``t`` ranks the contemporaneous leg positively
    and the forward leg negatively.
    """
    amplitude = 0.005 * (i + 1)
    contemporaneous = 0.01 * (i + 1)
    forward = 0.12 - 0.01 * i
    c0 = BASE
    c1 = c0 * (1.0 + contemporaneous)
    c2 = c1 * (1.0 + forward)
    series = {
        "2026-01": [c0 * (1.0 + 0.002 * s) for s in (0, 1, -1, 1, -1)] + [c0],
        "2026-02": [c0 * (1.0 + amplitude * s) for s in (0, 1, -1, 1, -1)] + [c1],
        "2026-03": [c1 * (1.0 + 0.002 * s) for s in (0, 1, -1, 1, -1)] + [c2],
    }
    dates: list[str] = []
    closes: list[float] = []
    volumes: list[float] = []
    for month in MONTHS:
        for date, close in zip(_month_dates(month), series[month], strict=True):
            dates.append(date)
            closes.append(round(close, 6))
            volumes.append(1.0)
    return {"dates": dates, "closes": closes, "volumes": volumes}


def _fixture_bars() -> dict:
    return {ticker: _bars_for_ticker(i) for i, ticker in enumerate(TICKERS)}


def _fixture_panel() -> list[dict]:
    return [{"ticker": ticker, "effective_date": "2026-02-16"} for ticker in TICKERS]


def _month_slice(bars: dict, month: str) -> tuple[list, list]:
    idx = [i for i, d in enumerate(bars["dates"]) if str(d).startswith(month)]
    return [bars["closes"][i] for i in idx], [bars["volumes"][i] for i in idx]


def _end_close(bars: dict, month: str) -> float:
    return _month_slice(bars, month)[0][-1]


def test_forward_window_not_contemporaneous():
    """The reported rank_ic is the forward leg (t+1), not the contemporaneous one."""
    bars = _fixture_bars()
    table = forward_rank_table(_fixture_panel(), bars_for=lambda t: bars[t], min_obs=MIN_OBS)

    signals = [kyle_lambda(*_month_slice(bars[t], "2026-02"), min_obs=MIN_OBS) for t in TICKERS]
    contemporaneous = [
        _end_close(bars[t], "2026-02") / _end_close(bars[t], "2026-01") - 1.0 for t in TICKERS
    ]
    forward = [
        _end_close(bars[t], "2026-03") / _end_close(bars[t], "2026-02") - 1.0 for t in TICKERS
    ]
    ic_contemporaneous = rank_ic(signals, contemporaneous)
    ic_forward = rank_ic(signals, forward)
    assert ic_contemporaneous > 0 > ic_forward, (
        "fixture premise: the contemporaneous and forward rank correlations must "
        "differ in sign, or this test cannot tell the two windows apart"
    )

    row = table["table"][0]
    assert row["month"] == "2026-02"
    assert table["window"]["return"] == "fwd_return_t+1"
    assert row["return_leg"] == "fwd_return_t+1"
    assert row["kyle_lambda_rank_ic"] == pytest.approx(ic_forward)
    assert row["kyle_lambda_rank_ic"] != pytest.approx(ic_contemporaneous)
    amihud = [amihud_illiquidity(*_month_slice(bars[t], "2026-02")) for t in TICKERS]
    assert row["amihud_illiquidity_rank_ic"] == pytest.approx(rank_ic(amihud, forward))


def test_undetermined_rows_read_unavailable():
    """A symbol-month whose trade direction cannot be determined is not zeroed."""
    bars = _fixture_bars()
    # T00 has a single bar in month t and none in t+1: the estimator cannot
    # determine a trade direction and the forward leg has no month-end close.
    bars["T00"] = {"dates": ["2026-02-02"], "closes": [100.0], "volumes": [1.0]}

    table = forward_rank_table(_fixture_panel(), bars_for=lambda t: bars[t], min_obs=MIN_OBS)

    obs = {o["ticker"]: o for o in table["observations"]}
    row = obs["T00"]
    assert row["status"] == "unavailable"
    assert row["kyle_lambda"] is None
    assert row["amihud_illiquidity"] is None
    assert row["forward_return"] is None
    assert row["reasons"], "an unavailable row names why"
    # A gap is one row, not the table: the remaining names still rank.
    assert obs["T01"]["status"] == "ok"
    assert table["status"] == "ok"
    assert table["table"][0]["n_unavailable"] == 1


def test_empty_panel_is_reported_not_crashed_on(tmp_path):
    """No panel at all is an honest `unavailable`, never an exception or a zero."""
    assert load_report_panel(tmp_path) == []
    table = forward_rank_table(load_report_panel(tmp_path), bars_for=lambda t: {})
    assert table["status"] == "unavailable"
    assert table["reason"]
    assert table["table"] == []
    assert table["window"]["return"] == "fwd_return_t+1"
    assert "unavailable" in render_text(table)
