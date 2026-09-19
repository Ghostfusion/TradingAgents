"""WP-10 - the measurement layer: the panel, the statistics, the redundancy.

Covers the plan's acceptance list (`docs/scores/IMPLEMENTATION_PLAN.md` section
7, WP-10, and its exit criteria in section 9, Phase C), one test per clause:

(a) a panel for a trading date exists on disk, carries its cost and coverage,
    is chunked to the vendor's 500-symbol cap, and a second invocation makes
    zero network calls;
(b) a panel below the cross-section floors is labelled
    `INSUFFICIENT_CROSS_SECTION` and produces **no weight vector** - while a
    panel above them produces one;
(c) a synthetic panel with a planted predictive factor produces a high rank IC
    and a monotone decile spread, and pure noise produces neither;
(d) per-factor IC / rank IC / ICIR / decile spread / monotonicity / turnover /
    persistence are emitted, with the OOS split and the multiple-testing
    checks (CPCV, deflated Sharpe, PBO, reality check, SPA);
(e) the redundancy matrix is emitted with the factor names, and the two named
    blocks (the 50% trend+momentum+RS block in `TechnicalScore` and the
    FCF-yield cluster in `FundamentalScore`) are reported with their pairwise
    correlations;
(f) the module never touches the sizing path, the risk governor, the gate
    precedence or `decision_guardrail`, and it prints no invented coefficient;
(g) the transport is injectable - the live SEC EDGAR fetch is the one thing
    that needs the network, and the mapping from EDGAR's annual facts to the
    canonical ``fin`` keys is exercised against recorded payload shapes.

Offline and deterministic: every panel, price series and vendor payload is
synthetic, and every stub records its own call count so "zero network calls"
is an assertion rather than a hope.
"""

from __future__ import annotations

import ast
import json
import math
import random
from pathlib import Path

import pytest

from scripts.score_panel import (
    CHUNK_SIZE,
    GAP_FPI_MARKET_CAP,
    META_KEY,
    REDUNDANT_ABS_CORR,
    SEC_REQUESTS_PER_SECOND,
    STATUS_ADVISORY,
    STATUS_RESEARCH_ONLY,
    FetchResult,
    PriceProvider,
    build_panel,
    canonical_fin_from_sec,
    engine_registry,
    engine_weight_vector,
    estimate_cost,
    evaluate_panel,
    load_panel_series,
    multiple_testing,
    panel_path,
    read_panel,
    render_text,
    sec_xbrl_transport,
    slice_bars,
    split_chunks,
    technical_rows_asof,
    write_panel,
)
from tradingagents.strategies import alpha_health


# --------------------------------------------------------------------------
# Synthetic fixtures: a planted factor, a noise factor, and a stub transport
# --------------------------------------------------------------------------

DATES = [f"2026-09-{d:02d}" for d in range(1, 26)]
UNIVERSE = [f"T{i:03d}" for i in range(120)]
NOISE_METRICS = ("earnings_yield", "price_to_earnings", "adx", "roc20")


def _truth(seed: int = 7) -> dict:
    rng = random.Random(seed)
    return {t: rng.gauss(0.0, 1.0) for t in UNIVERSE}


def _planted_panel(truth: dict, *, dates=DATES, noise_seed: int = 11) -> dict:
    """A panel where ``fcf_yield`` carries the planted signal and the rest is noise.

    ``fcf_yield`` is a positive yield (so the cluster's own identity
    ``1 / price_to_free_cash_flow`` is a monotone transform of it), and each
    name's ``close`` drifts with the planted signal, which is where the forward
    return the statistics are measured against comes from.
    """
    rng = random.Random(noise_seed)
    noise = {t: {m: [rng.gauss(0.0, 1.0) for _ in dates] for m in NOISE_METRICS}
             for t in UNIVERSE}
    jitter = {t: [rng.gauss(0.0, 0.004) for _ in dates] for t in UNIVERSE}
    out: dict = {}
    for i, date in enumerate(dates):
        rows: dict = {}
        for t in UNIVERSE:
            row = {m: noise[t][m][i] for m in NOISE_METRICS}
            row["fcf_yield"] = 0.05 * math.exp(0.3 * truth[t])
            row["close"] = round(
                50.0 * math.exp(0.004 * truth[t] * i + jitter[t][i]), 6)
            rows[t] = row
        out[date] = rows
    return out


class Transport:
    """A stub transport: deterministic canonical financials plus a call counter.

    It returns **canonical ``fin`` dicts, not panel rows**, because that is the
    transport's contract: the builder assembles the row (``panel_row_from_fin``)
    once both legs are in hand, so the valuation block can use the close. A stub
    that handed back finished rows would bypass the very derivation the panel
    depends on - and would silently stop exercising it.
    """

    def __init__(self, factor_seed: int = 3):
        self.calls = 0
        self.api_calls = 0
        self.requested: list[str] = []
        self._rng = random.Random(factor_seed)
        self._fins: dict[str, dict] = {}

    def _fin(self, ticker: str) -> dict:
        # any symbol gets a fin, so a larger universe is a real fetch, not gaps
        if ticker not in self._fins:
            r = self._rng
            scale = 1.0 + 0.25 * r.gauss(0, 1)
            self._fins[ticker] = {
                "revenue": {"current": 1000.0 * scale, "prior": 900.0 * scale},
                "net_income": {"current": 100.0 * scale, "prior": 90.0 * scale},
                "operating_income": {"current": 150.0 * scale, "prior": 140.0 * scale},
                "gross_profit": {"current": 400.0 * scale, "prior": 380.0 * scale},
                "total_assets": {"current": 2000.0 * scale, "prior": 1900.0 * scale},
                "total_liabilities": {"current": 1200.0 * scale, "prior": 1150.0 * scale},
                "total_equity": {"current": 800.0 * scale, "prior": 750.0 * scale},
                "current_assets": {"current": 700.0 * scale, "prior": 650.0 * scale},
                "current_liabilities": {"current": 400.0 * scale, "prior": 380.0 * scale},
                "inventory": {"current": 100.0 * scale, "prior": 95.0 * scale},
                "cash": {"current": 150.0 * scale, "prior": 140.0 * scale},
                "total_debt": {"current": 500.0 * scale, "prior": 480.0 * scale},
                "operating_cashflow": {"current": 200.0 * scale, "prior": 180.0 * scale},
                "capex": {"current": 50.0 * scale, "prior": 45.0 * scale},
                "depreciation": {"current": 60.0 * scale, "prior": 55.0 * scale},
                "eps": {"current": 2.0 * scale, "prior": 1.8 * scale},
                "shares_outstanding": 1e8,
                "market_cap": 4e9 * scale,
            }
        return dict(self._fins[ticker])

    def __call__(self, chunk, date):
        self.calls += 1
        self.requested.extend(chunk)
        self.api_calls += len(chunk)
        return FetchResult(
            fins={t: self._fin(t) for t in chunk},
            requests=1,
            api_calls=len(chunk),
            symbols_requested=len(chunk),
            gaps={},
        )


def _bars(dates, drift: float, seed: int, noise: float = 0.002) -> dict:
    rng = random.Random(seed)
    closes = [50.0]
    for _ in range(1, len(dates)):
        closes.append(round(closes[-1] * (1 + drift + rng.gauss(0, noise)), 4))
    return {
        "dates": list(dates),
        "closes": closes,
        "highs": [round(c * 1.01, 4) for c in closes],
        "lows": [round(c * 0.99, 4) for c in closes],
        "volumes": [int(1e6 + i) for i in range(len(dates))],
        "opens": list(closes),
    }


# --------------------------------------------------------------------------
# (a) the panel exists, with its cost and coverage, chunked and cached
# --------------------------------------------------------------------------


def test_a_panel_for_a_trading_date_exists_with_its_cost_and_coverage(tmp_path):
    transport = Transport()
    big = [f"T{i:04d}" for i in range(1100)]
    build = build_panel([DATES[0]], big, transport=transport, cache_dir=str(tmp_path))

    path = panel_path(str(tmp_path), DATES[0])
    assert Path(path).exists(), "the panel file is the deliverable"
    rows, meta = read_panel(path)
    assert rows, "the panel carries names"
    assert meta["fetched_at"], "the fetch timestamp is recorded"
    assert meta["cost"]["api_calls"] > 0 and meta["cost"]["model"], "the call cost is recorded"
    assert build["cost"]["api_calls"] == 1100, "one request per filer"
    assert build["coverage"]["names_present"] == 1100
    assert build["coverage"]["ratio"] == 1.0
    # every metric cell is a real number, never a 0 standing in for NA
    assert all(isinstance(v, (int, float)) for r in rows.values() for v in r.values())
    assert META_KEY not in rows


def test_a_second_invocation_makes_zero_network_calls(tmp_path):
    transport = Transport()
    first = build_panel(DATES, UNIVERSE, transport=transport, cache_dir=str(tmp_path))
    assert transport.calls == len(DATES)
    before = transport.calls
    second = build_panel(DATES, UNIVERSE, transport=transport, cache_dir=str(tmp_path))
    assert transport.calls == before, "a cached date is never re-fetched"
    assert second["cost"]["requests"] == 0 and second["cost"]["api_calls"] == 0
    assert second["cost"]["cache_hits"] == len(DATES)
    assert first["coverage"] == second["coverage"]


def test_the_universe_is_chunked_for_batching_and_the_estimate_is_what_runs(tmp_path):
    transport = Transport()
    big = [f"T{i:04d}" for i in range(1100)]
    build = build_panel([DATES[0]], big, transport=transport, cache_dir=str(tmp_path))
    assert len(transport.requested) == 1100
    assert transport.calls == 3, "the batch size is 500 => 500 + 500 + 100"
    est = estimate_cost(1100)
    assert est["source"].startswith("SEC EDGAR XBRL")
    assert est["chunks"] == 3 and est["api_calls"] == 1100, "one request per filer"
    assert [len(c) for c in split_chunks([f"X{i}" for i in range(1100)])] == [500, 500, 100]
    # the estimate is what the run actually spends
    assert build_panel([DATES[1]], big, transport=Transport(),
                       cache_dir=str(tmp_path))["cost"]["api_calls"] == est["api_calls"]


def test_the_cost_does_not_grow_with_the_number_of_dates(monkeypatch):
    """The companyfacts payload is per-FILER, so a 30-date panel is one request
    a name, not thirty. That property lives in the transport, and it is what
    makes a 464-name panel affordable: without it the same multi-MB payload
    would be re-fetched for every date."""
    from tradingagents.dataflows import sec_edgar

    calls: list[str] = []

    def _fake(ticker, years=15):
        calls.append(ticker)
        return _facts({"Total assets": {"2025-06-30": (2e9, "2025-08-01")},
                       "Net income (loss)": {"2025-06-30": (1e8, "2025-08-01")}})

    monkeypatch.setattr(sec_edgar, "annual_facts", _fake)
    transport = sec_xbrl_transport(rate_limit=0)  # no pacing in a test
    first = transport(["AAPL", "MSFT"], DATES[0])
    assert calls == ["AAPL", "MSFT"] and first.requests == 2
    second = transport(["AAPL", "MSFT"], DATES[1])
    assert calls == ["AAPL", "MSFT"], "the payload is cached across dates"
    assert second.requests == 0 and second.api_calls == 0
    assert set(second.fins) == {"AAPL", "MSFT"}, "and the fins still come back"


def test_the_transport_records_a_name_it_cannot_supply(monkeypatch):
    """No CIK, no facts: a named gap, and the rest of the batch is unaffected."""
    from tradingagents.dataflows import sec_edgar

    def _fake(ticker, years=15):
        if ticker == "NOPE":
            raise sec_edgar.NoMarketDataError(ticker, detail="no CIK found on EDGAR")
        return _facts({"Total assets": {"2025-06-30": (2e9, "2025-08-01")}})

    monkeypatch.setattr(sec_edgar, "annual_facts", _fake)
    res = sec_xbrl_transport(rate_limit=0)(["AAPL", "NOPE"], DATES[0])
    assert set(res.fins) == {"AAPL"}
    assert "no CIK" in res.gaps["NOPE"]
    assert res.symbols_requested == 2


def test_a_name_with_no_facts_is_recorded_as_a_gap_not_dropped(tmp_path):
    """A filer with no 10-K/20-F/40-F facts (pre-XBRL, IFRS, or no CIK) is a
    named gap. It must never vanish silently: a panel that loses a third of its
    universe to a coverage limit has to say so."""
    class _Gappy(Transport):
        def __call__(self, chunk, date):
            res = super().__call__(chunk, date)
            gaps = {t: "no annual XBRL facts on EDGAR" for t in chunk[:2]}
            return res._replace(fins={t: f for t, f in res.fins.items()
                                      if t not in gaps}, gaps=gaps)

    build = build_panel([DATES[0]], UNIVERSE, transport=_Gappy(), cache_dir=str(tmp_path))
    assert build["gaps"] == 2, "the build reports the count"
    rows, meta = read_panel(panel_path(str(tmp_path), DATES[0]))
    assert meta["fundamentals_gaps"] == {
        UNIVERSE[0]: "no annual XBRL facts on EDGAR",
        UNIVERSE[1]: "no annual XBRL facts on EDGAR",
    }, "the panel file carries the reasons, so a thin cross-section reads as thin"
    assert UNIVERSE[0] not in rows and UNIVERSE[2] in rows
    assert "fundamentals gaps" in render_text({"panel": {}}, build)


def test_an_empty_fetch_is_not_cached_as_a_panel(tmp_path):
    class _Empty(Transport):
        def __call__(self, chunk, date):
            self.calls += 1
            return FetchResult(fins={}, requests=len(chunk), api_calls=len(chunk),
                               symbols_requested=len(chunk), gaps={})

    empty = _Empty()

    build = build_panel([DATES[0]], UNIVERSE, transport=empty, cache_dir=str(tmp_path))
    assert not Path(panel_path(str(tmp_path), DATES[0])).exists()
    assert build["per_date"][DATES[0]]["source"] == "empty-fetch"
    # the date is retried rather than served from a poisoned cache
    again = build_panel([DATES[0]], UNIVERSE, transport=Transport(), cache_dir=str(tmp_path))
    assert again["cost"]["cache_hits"] == 0
    assert again["per_date"][DATES[0]]["n_names"] == len(UNIVERSE)


def test_slice_bars_keeps_only_bars_up_to_the_date():
    series = _bars(DATES, drift=0.001, seed=5)
    sliced = slice_bars(series, DATES[4])
    assert sliced["dates"] == DATES[:5]
    assert sliced["closes"] == series["closes"][:5]
    assert len(sliced["volumes"]) == 5
    # an unorderable series is refused rather than sliced on a guess
    assert slice_bars({"dates": [1, 2], "closes": [1.0, 2.0]}, "2026-09-01") == {}
    assert slice_bars({"dates": [], "closes": []}, DATES[0]) == {}


# --------------------------------------------------------------------------
# (b) the label, and no weight vector below the floors
# --------------------------------------------------------------------------


def test_a_panel_below_the_floors_is_labelled_insufficient_and_produces_no_weight_vector():
    small = {d: {f"S{i}": {"fcf_yield": float(i)} for i in range(5)} for d in DATES[:3]}
    report = evaluate_panel(small, dates=DATES[:3])
    assert report["panel"]["status"] == alpha_health.CROSS_SECTION_INSUFFICIENT
    assert report["weight_vector"]["produced"] is False
    assert report["weight_vector"]["vectors"] is None, "below the floors: no vector"
    assert "INSUFFICIENT_CROSS_SECTION" in json.dumps(report)
    # the reason names the floor that failed, not a shrug
    assert "min_periods" in report["panel"]["status_reason"]


def test_a_panel_above_the_floors_produces_a_vector_labelled_research_only():
    report = evaluate_panel(_planted_panel(_truth()), dates=DATES)
    assert report["panel"]["status"] == alpha_health.CROSS_SECTION_OK
    assert report["weight_vector"]["produced"] is True
    vectors = report["weight_vector"]["vectors"]
    assert vectors and "technical_score" in vectors
    assert report["weight_vector"]["status"] == STATUS_RESEARCH_ONLY


def test_the_label_is_a_tested_output_not_a_constant():
    """Dropping the label - or flipping it - must fail, in both directions."""
    tiny = evaluate_panel(DATES[:2] and {d: {"A": {"fcf_yield": 1.0}} for d in DATES[:2]},
                          dates=DATES[:2])
    big = evaluate_panel(_planted_panel(_truth()), dates=DATES)
    assert tiny["panel"]["status"] != big["panel"]["status"], (
        "a floor that never fires is not a floor: the label must move with the panel"
    )
    assert tiny["weight_vector"]["produced"] is False
    assert big["weight_vector"]["produced"] is True
    # a single name per cross-section is insufficient even over many periods
    thin = evaluate_panel({d: {"A": {"fcf_yield": 1.0}} for d in DATES}, dates=DATES)
    assert thin["panel"]["status"] == alpha_health.CROSS_SECTION_INSUFFICIENT
    assert thin["weight_vector"]["produced"] is False


# --------------------------------------------------------------------------
# (c) a planted factor is measured; noise is not
# --------------------------------------------------------------------------


def test_a_planted_predictive_factor_has_a_high_rank_ic_and_a_monotone_decile_spread():
    report = evaluate_panel(_planted_panel(_truth()), dates=DATES, n_buckets=10)
    planted = report["factors"]["fcf_yield"]
    assert planted["measured"] is True
    assert planted["rows"]["ic"]["mean_rank_ic"] > 0.3
    assert planted["ic_label"] == "STRONG"
    deciles = planted["rows"]["deciles"]
    assert deciles["ordering"]["ordered_pairs"] == 9
    assert deciles["ordering"]["monotone"] is True
    assert deciles["spread"] > 0.0


def test_pure_noise_produces_neither_a_high_ic_nor_a_monotone_spread():
    report = evaluate_panel(_planted_panel(_truth()), dates=DATES)
    noise = report["factors"]["adx"]
    planted_ic = abs(report["factors"]["fcf_yield"]["rows"]["ic"]["mean_rank_ic"])
    assert abs(noise["rows"]["ic"]["mean_rank_ic"]) < 0.15
    assert abs(noise["rows"]["ic"]["mean_rank_ic"]) < planted_ic / 3
    assert all(
        (m is None) or abs(m) < 0.05
        for m in (noise["rows"]["deciles"]["bucket_means"] or [])
    )


# --------------------------------------------------------------------------
# (d) the statistics, the OOS split and the multiple-testing checks
# --------------------------------------------------------------------------


def test_per_factor_statistics_are_emitted_with_the_oos_split_and_the_checks():
    report = evaluate_panel(_planted_panel(_truth()), dates=DATES)
    row = report["factors"]["fcf_yield"]
    rows = row["rows"]
    # the harness' five rows, each with its n
    assert rows["ic"]["mean_rank_ic"] is not None and rows["ic"]["ic_ir"] is not None
    assert rows["ic"]["mean_pearson_ic"] is not None
    assert rows["deciles"]["spread"] is not None
    assert rows["deciles"]["ordering"]["fraction"] is not None
    assert rows["coverage"]["ratio"] is not None
    assert rows["stability"]["persistence"] is not None
    assert rows["turnover"]["mean_turnover"] is not None
    assert all(r.get("n") is not None for r in
               (rows["ic"], rows["deciles"], rows["coverage"], rows["stability"],
                rows["turnover"]))
    # the OOS split, from evaluate.oos_split
    mt = row["multiple_testing"]
    assert mt["oos"]["train_periods"] > 0 and mt["oos"]["oos_periods"] > 0
    assert mt["oos"]["label"] in ("SIGN_HOLDS", "SIGN_FLIPS", "FLAT", "UNMEASURED")
    assert mt["oos"]["basis"].startswith("evaluate.oos_split")
    assert mt["oos"]["label"] == "SIGN_HOLDS", "the planted factor keeps its sign"
    # a stable NEGATIVE IC is a signal, not a failure: the label is about sign
    negative = multiple_testing({"rank_ic": [-0.2] * 10, "spread": [-0.01] * 10},
                                n_trials=2)
    assert negative["oos"]["label"] == "SIGN_HOLDS"
    # the multiple-testing checks
    assert mt["deflated_sharpe"]["n_trials"] == report["family"]["n_factors"]
    assert mt["deflated_sharpe"]["value"] is not None
    assert mt["cpcv"]["n_folds"] > 0
    assert mt["cpcv"]["overfit_mask"] in (True, False)
    family = report["family"]
    assert family["pbo"]["flag"] in (True, False)
    assert family["reality_check"]["p_value"] is not None
    assert family["spa"]["p_value"] is not None


def test_the_row_floors_still_withhold_a_row_and_state_the_reason():
    """A 3-period panel prints an unavailable row, never a number."""
    rows = alpha_health.score_evaluation_rows(
        {d: {"A": 1.0, "B": 2.0} for d in DATES[:3]},
        {"A": [1.0, 1.1, 1.2], "B": [2.0, 1.9, 1.8]}, holding=1, n_buckets=2,
    )
    assert rows["ic"]["available"] is False
    assert rows["ic"]["reason"] and rows["ic"]["n"] == 0
    assert rows["status"] == alpha_health.CROSS_SECTION_INSUFFICIENT


def test_na_is_not_zero_for_the_panel_metrics():
    panel = _planted_panel(_truth(), dates=DATES)
    # half the names lose the factor at every date: they leave the denominator
    for d, rows in panel.items():
        for t in sorted(rows)[: len(rows) // 2]:
            rows[t].pop("fcf_yield", None)
    report = evaluate_panel(panel, dates=DATES)
    measured = report["factors"]["fcf_yield"]
    assert measured["n_observations"] == len(DATES) * (len(UNIVERSE) // 2)
    assert measured["rows"]["coverage"]["scored"] < measured["rows"]["coverage"]["universe"]


def test_decile_spread_and_ordering_are_withheld_without_both_ends():
    assert alpha_health.decile_spread([None, 0.01, 0.02]) is None
    assert alpha_health.decile_spread([0.01, None, 0.02]) == pytest.approx(0.01)
    ordering = alpha_health.decile_ordering([0.0, 0.1, None, 0.0, 0.4])
    assert ordering["adjacent_pairs"] == 4, "the denominator is every adjacent pair"
    assert ordering["populated_pairs"] == 2
    assert ordering["ordered_pairs"] == 2, "an unpopulated pair is NOT ordered"
    assert ordering["sparse"] is True, "an empty table is not a bad ordering"
    assert ordering["monotone"] is False
    dense = alpha_health.decile_ordering([0.0, 0.1, 0.2, 0.3])
    assert dense["sparse"] is False and dense["monotone"] is True


def test_a_non_finite_rank_ic_is_withheld_never_printed_as_nan():
    """A tie-collapsed (boolean) factor must not print `nan` as its IC."""
    dates = [f"2026-09-{d:02d}" for d in range(1, 9)]
    scores = {d: {str(t): float(t % 2) for t in range(20)} for d in dates}
    prices = {str(t): [1.0 + 0.01 * i for i in range(len(dates))] for t in range(20)}
    rows = alpha_health.score_evaluation_rows(scores, prices, holding=1, n_buckets=5,
                                              min_names=4, min_obs=2)
    assert rows["ic"]["available"] is False, "nan is not an IC"
    assert "non-finite" in rows["ic"]["reason"]


def test_the_deflated_sharpe_of_a_spread_series_is_never_a_complex_number():
    """A long-short SPREAD can lose more than 100% in one period.

    `evaluate.cagr` compounded it into a negative base, and `base ** (1/years)`
    returned a **complex** number, which then reached the report as
    `(-2.7667+0.0002j)`. Both halves are asserted: the root cause (cagr) and the
    layer's refusal to print it.
    """
    from tradingagents.strategies import evaluate

    spread = [-1.4, 0.2, -0.3, 0.1, -0.2, 0.05, -0.1, 0.3]
    assert isinstance(evaluate.cagr(spread), float), "cagr promises a float"
    assert evaluate.cagr([-1.0, -1.0]) == -1.0, "a total loss is -100%/yr"
    dsr = evaluate.deflated_sharpe(spread, n_trials=5)
    assert isinstance(dsr, float)
    out = multiple_testing({"rank_ic": [0.1] * len(spread), "spread": spread},
                                     n_trials=5)
    assert out["deflated_sharpe"]["value"] is None
    assert "not a real number" in out["deflated_sharpe"]["note"]


def test_the_deflated_sharpe_carries_a_note_when_the_spread_has_no_dispersion():
    series = {"rank_ic": [0.1, 0.2, 0.15], "spread": [0.01, 0.01, 0.01]}
    out = multiple_testing(series, n_trials=3)
    assert out["deflated_sharpe"]["value"] is not None
    assert out["deflated_sharpe"]["stdev_spread"] == 0.0
    assert "float noise" in out["deflated_sharpe"]["note"]


# --------------------------------------------------------------------------
# (e) the redundancy matrix and the two named blocks
# --------------------------------------------------------------------------


def test_the_redundancy_matrix_is_emitted_with_the_factor_names():
    report = evaluate_panel(_planted_panel(_truth()), dates=DATES)
    matrix = report["redundancy"]
    names = {n for key in matrix["pairs"] for n in key.split("|")}
    assert matrix["n_measured"] >= 5
    assert {"fcf_yield", "earnings_yield", "adx", "roc20"} <= names
    assert "close" not in names, "a price level is not a factor"
    pair = matrix["pairs"]["adx|roc20"]
    assert -1.0 <= pair["spearman"] <= 1.0
    assert pair["n"] == len(DATES) * len(UNIVERSE)
    assert pair["redundant"] is False


def test_the_trend_momentum_rs_block_is_reported_with_its_pairwise_correlations():
    panel = _planted_panel(_truth(), dates=DATES)
    # make the block's members one bet by construction, as the plan says they are
    for rows in panel.values():
        for t, row in rows.items():
            row["roc20"] = row["adx"] * 0.5
            row["rsi"] = row["adx"] * -0.25 + 0.1
    report = evaluate_panel(panel, dates=DATES)
    block = report["redundancy"]["blocks"]["technical_trend_momentum_relative_strength"]
    assert block["weight_share"] == 50.0
    assert {"adx", "roc20", "rsi"} <= set(block["measured"])
    assert block["n_pairs"] == 3, "three measured members -> three pairs"
    assert abs(block["pairs"]["adx|roc20"]["spearman"]) >= 0.99
    assert block["redundant_pairs"], "a near-duplicate pair is flagged"
    assert block["max_abs_spearman"] >= REDUNDANT_ABS_CORR
    assert "trend + momentum + relative strength" in block["reason"]
    # the engine's own table puts 50% on exactly those three categories
    weights = engine_weight_vector("technical_score", engine_registry())["weights"]
    assert weights["trend"] + weights["momentum"] + weights["relative_strength"] == 50.0


def test_the_fcf_yield_cluster_is_reported_with_its_pairwise_correlations():
    panel = _planted_panel(_truth(), dates=DATES)
    for rows in panel.values():
        for t, row in rows.items():
            row["price_to_free_cash_flow"] = 1.0 / row["fcf_yield"]
            row["price_to_cash_flow"] = 2.0 / row["fcf_yield"]
    report = evaluate_panel(panel, dates=DATES)
    block = report["redundancy"]["blocks"]["fundamental_fcf_yield_cluster"]
    assert block["n_pairs"] >= 3
    assert abs(block["pairs"]["fcf_yield|price_to_free_cash_flow"]["spearman"]) >= 0.99
    assert "fcf_yield|price_to_free_cash_flow" in block["redundant_pairs"]
    assert "FCF-yield" in block["reason"]
    # val_z is declared by the cluster and is NOT on the panel path: it is
    # reported missing rather than correlated with something it is not
    assert "val_z" in block["missing"]


def test_a_redundant_factor_is_marked_and_the_category_verdict_follows():
    panel = _planted_panel(_truth(), dates=DATES)
    for rows in panel.values():
        for t, row in rows.items():
            row["earnings_yield"] = row["fcf_yield"]
    report = evaluate_panel(panel, dates=DATES)
    assert report["factors"]["earnings_yield"]["redundant"] is True
    assert report["factors"]["earnings_yield"]["redundant_with"]
    vs = report["engines"]["fundamental_score"]["categories"]["VS"]
    assert "earnings_yield" not in vs["survived"] or "fcf_yield" in vs["survived"]


# --------------------------------------------------------------------------
# (f) never a gate, never a size, no invented coefficient, no guardrail band
# --------------------------------------------------------------------------


def test_the_module_never_touches_the_sizing_path():
    """No import and no attribute access on the sizing path or the guardrail."""
    tree = ast.parse(Path("scripts/score_panel.py").read_text(encoding="utf-8"))
    referenced: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            referenced.update(a.name for a in node.names)
        elif isinstance(node, ast.ImportFrom):
            referenced.add(node.module or "")
            referenced.update(f"{node.module}.{a.name}" for a in node.names)
        elif isinstance(node, ast.Attribute):
            parts = []
            cur = node
            while isinstance(cur, ast.Attribute):
                parts.append(cur.attr)
                cur = cur.value
            if isinstance(cur, ast.Name):
                parts.append(cur.id)
                referenced.add(".".join(reversed(parts)))
    for forbidden in ("sizing", "risk.sizing", "risk_multiplier", "knife_guard",
                      "position_size", "decision_guardrail", "GATE_PRECEDENCE",
                      "risk_governor", "SCORE_BANDS"):
        assert not any(forbidden in ref for ref in referenced), (forbidden, referenced)


def test_no_weight_vector_is_invented_and_the_equal_weight_engine_says_so():
    registry = engine_registry()
    fundamental = engine_weight_vector("fundamental_score", registry)
    assert fundamental["weights"] == {"FQS": 0.25, "FGS": 0.25, "VS": 0.25, "FRS": 0.25}
    assert "no validated vector published" in fundamental["basis"]
    assert fundamental["status"] == STATUS_RESEARCH_ONLY
    technical = engine_weight_vector("technical_score", registry)
    from tradingagents.strategies.technical_score import CATEGORY_WEIGHTS

    assert technical["weights"] == CATEGORY_WEIGHTS, "the printed vector is the table used"
    assert abs(sum(technical["share"].values()) - 1.0) < 1e-9
    missing = engine_weight_vector("news_score", registry)
    assert missing["weights"] is None and missing["status"] == "UNMEASURED"


def test_the_status_vocabulary_is_advisory_and_research_only():
    report = evaluate_panel(_planted_panel(_truth()), dates=DATES)
    assert report["status"] == STATUS_ADVISORY
    assert report["factors"]["fcf_yield"]["status"] == STATUS_ADVISORY
    assert report["weight_vector"]["status"] == STATUS_RESEARCH_ONLY
    for engine in report["engines"].values():
        assert engine["weight_vector"]["status"] in (
            STATUS_RESEARCH_ONLY, "UNMEASURED")


def test_an_engine_whose_module_is_absent_is_reported_not_omitted():
    registry = engine_registry()
    assert registry["fundamental_score"]["available"] is True
    assert registry["technical_score"]["available"] is True
    absent = [name for name, e in registry.items() if not e["available"]]
    assert absent, "at least one engine of the map has no module in this tree"
    for name in absent:
        assert registry[name]["reason"], f"{name} must state why it is UNMEASURED"
    assert "event_state" in registry and "state" in registry["event_state"]["reason"]


def test_a_sibling_engine_module_is_picked_up_by_the_registry(monkeypatch):
    """The registry reads a new engine's own COMPONENTS table, whatever it names."""
    import sys
    import types

    from scripts import score_panel as sp

    mod = types.ModuleType("tradingagents.strategies.sentiment_score")
    mod.COMPONENTS = {"sent_x": type("C", (), {"category": "level", "direction": "higher_better"})()}
    mod.CATEGORY_WEIGHTS = {"level": 100.0}
    mod.CATEGORY_COMPONENTS = {"level": ("sent_x",)}
    monkeypatch.setitem(sys.modules, "tradingagents.strategies.sentiment_score", mod)
    registry = sp.engine_registry()
    assert registry["sentiment_score"]["available"] is True
    assert registry["sentiment_score"]["factors"]["sent_x"]["category"] == "level"
    assert engine_weight_vector("sentiment_score", registry)["weights"] == {"level": 100.0}


# --------------------------------------------------------------------------
# (g) the source leg: injectable transport, one honest mapping
# --------------------------------------------------------------------------


def _facts(series: dict, shares: dict | None = None) -> dict:
    """An ``sec_edgar.annual_facts``-shaped payload from ``{label: {end: (val, filed)}}``."""
    return {
        "series": {
            label: {end: {"val": v, "filed": f} for end, (v, f) in by_end.items()}
            for label, by_end in series.items()
        },
        "shares": shares or {},
        "span": None,
        "years": 15,
    }


def test_the_sec_facts_map_to_canonical_financials_with_no_fabrication():
    fin = canonical_fin_from_sec(_facts({
        "Revenue": {"2025-06-30": (1000.0, "2025-08-01"),
                    "2024-06-30": (900.0, "2024-08-01")},
        "Net income (loss)": {"2025-06-30": (100.0, "2025-08-01"),
                              "2024-06-30": (90.0, "2024-08-01")},
        "Total assets": {"2025-06-30": (2000.0, "2025-08-01"),
                         "2024-06-30": (1900.0, "2024-08-01")},
        "Capex (-)": {"2025-06-30": (50.0, "2025-08-01"),
                      "2024-06-30": (45.0, "2024-08-01")},
        "Long-term debt": {"2025-06-30": (500.0, "2025-08-01")},
        "Long-term debt, current": {"2025-06-30": (80.0, "2025-08-01")},
    }))
    assert fin["revenue"] == {"current": 1000.0, "prior": 900.0}, "current/prior pairs"
    assert fin["net_income"]["current"] == 100.0
    assert fin["capex"]["current"] == 50.0, (
        "the SEC files capex as a positive outflow, which is the sign "
        "compute_ratios subtracts under abs()")
    assert fin["total_debt"]["current"] == 580.0, "borrowings = long-term + current portion"
    assert "market_cap" not in fin, "EDGAR has no price: a market cap is never invented"
    assert "ebitda" not in fin, "an absent field is absent, never 0"
    assert canonical_fin_from_sec({}) == {}
    assert canonical_fin_from_sec(_facts({})) == {}


def test_the_sec_read_is_point_in_time_so_a_panel_cannot_see_the_future():
    """A 10-K filed after the panel date is not a fact that date could know.

    Using it would be look-ahead bias, and it is the one error that would make
    every measured IC in this layer too good to be true.
    """
    facts = _facts({
        "Revenue": {"2025-06-30": (1000.0, "2025-08-01"),
                    "2026-06-30": (1400.0, "2026-08-05")},
        "Total assets": {"2025-06-30": (2000.0, "2025-08-01"),
                         "2026-06-30": (2400.0, "2026-08-05")},
    })
    before = canonical_fin_from_sec(facts, asof="2026-07-01")
    assert before["revenue"]["current"] == 1000.0, "the FY2026 report was not filed yet"
    after = canonical_fin_from_sec(facts, asof="2026-09-17")
    assert after["revenue"]["current"] == 1400.0, "once filed, it is the current year"
    assert after["revenue"]["prior"] == 1000.0
    assert canonical_fin_from_sec(facts, asof="2025-07-01") == {}, (
        "before the first filing there is nothing to read - empty, not zero")


def test_every_leg_is_aligned_to_one_fiscal_year_never_a_stale_substitute():
    """A tag last filed in 2013 must not sit beside a 2025 balance sheet.

    Mixed-vintage rows look measured and are not, so a label with no value at
    the reference year end is absent rather than carried over from another year.
    """
    fin = canonical_fin_from_sec(_facts({
        "Total assets": {"2025-06-30": (2000.0, "2025-08-01")},
        "Net income (loss)": {"2025-06-30": (100.0, "2025-08-01")},
        "Inventory": {"2013-12-31": (33.0, "2014-02-01")},
    }))
    assert fin["total_assets"]["current"] == 2000.0
    assert "inventory" not in fin, "the 2013 inventory is not the 2025 inventory"


def test_the_share_count_is_read_at_its_own_newest_eligible_period():
    """The cover-page count is far fresher than the fiscal-year balance, and it
    is the leg a market capitalisation needs - so it is selected on its own
    period ends, under the same point-in-time rule."""
    facts = _facts({"Total assets": {"2025-06-30": (2000.0, "2025-08-01")}},
                   shares={"2026-04-23": {"val": 7.42e9, "filed": "2026-04-25"},
                           "2026-07-23": {"val": 7.43e9, "filed": "2026-07-25"}})
    assert canonical_fin_from_sec(facts, asof="2026-05-01")["shares_outstanding"] == 7.42e9
    assert canonical_fin_from_sec(facts, asof="2026-09-17")["shares_outstanding"] == 7.43e9


def test_the_panel_derives_market_cap_from_its_own_close_and_the_sec_share_count(tmp_path):
    """EDGAR carries no price, so the valuation block would be NA for every name
    without this join. The panel has both halves - its close and the cover-page
    count - and the row is assembled once they meet.

    Asserted against a control run with no price leg: the price-based ratios are
    the observable difference, and they must be ABSENT without the close rather
    than present-but-invented.
    """
    class _NoCap(Transport):
        def _fin(self, ticker):
            fin = super()._fin(ticker)
            fin.pop("market_cap", None)
            fin["shares_outstanding"] = 2e8
            return fin

    series = {t: _bars(DATES, drift=0.001, seed=30 + i, noise=0.0)
              for i, t in enumerate(UNIVERSE)}
    provider = PriceProvider(loader=lambda t: series.get(t, {}))

    with_price = str(tmp_path / "with")
    build_panel([DATES[0]], UNIVERSE, transport=_NoCap(), price_provider=provider,
                technical=False, cache_dir=with_price)
    rows, _meta = read_panel(panel_path(with_price, DATES[0]))
    row = rows[UNIVERSE[0]]
    close = row["close"]
    assert row["price_to_earnings"] is not None, (
        "the close joined the SEC share count into a market cap, so the "
        "price-based ratios are reachable instead of permanently NA")
    assert row["price_to_book"] is not None

    without_price = str(tmp_path / "without")
    build_panel([DATES[0]], UNIVERSE, transport=_NoCap(), cache_dir=without_price)
    bare, _meta = read_panel(panel_path(without_price, DATES[0]))
    assert "price_to_earnings" not in bare[UNIVERSE[0]], (
        "no close => no market cap => the ratio is absent, never fabricated")
    assert "f" in bare[UNIVERSE[0]], "the statement-only metrics still measure"
    assert close > 0, "the control and the treatment differ only by the price leg"


def test_a_foreign_private_issuers_market_cap_is_withheld_never_guessed(tmp_path):
    """SIMO 2026-09-17, reproduced as a contract.

    A 20-F/40-F filer's US-listed line may be an ADS whose ratio EDGAR does not
    carry, so the traded close is per-ADS while the cover-page count is per
    **ordinary** share - and the product is wrong by that ratio. Measured live:
    1 ADS = 4 ordinary shares, so the panel derived **$34.0B** against a real
    **$8.1-8.6B**, P/E **277.28** against ~69 and P/B **40.93** against ~10, with
    Altman Z's X4 inflated alongside them. A wrong market cap poisons every
    price-based ratio, so it is withheld and the reason named.

    The domestic name in the same run is the control: the rule is scoped to the
    foreign filer, not a blanket removal of the valuation block.
    """
    fpi = UNIVERSE[0]

    class _Mixed(Transport):
        def _fin(self, ticker):
            fin = super()._fin(ticker)
            fin.pop("market_cap", None)
            fin["shares_outstanding"] = 2e8
            if ticker == fpi:
                fin["foreign_private_issuer"] = True
            return fin

    series = {t: _bars(DATES, drift=0.001, seed=60 + i, noise=0.0)
              for i, t in enumerate(UNIVERSE)}
    provider = PriceProvider(loader=lambda t: series.get(t, {}))
    out = str(tmp_path / "fpi")
    build_panel([DATES[0]], UNIVERSE, transport=_Mixed(), price_provider=provider,
                technical=False, cache_dir=out)
    rows, meta = read_panel(panel_path(out, DATES[0]))

    foreign = rows[fpi]
    assert foreign.get("close") is not None, "the price leg still ran for this name"
    assert "market_cap" not in foreign
    assert foreign.get("price_to_earnings") is None, (
        "the ratio needs a market cap, and no honest one exists here")
    assert foreign.get("price_to_book") is None
    assert meta["fundamentals_gaps"][fpi] == GAP_FPI_MARKET_CAP

    domestic = next(t for t in UNIVERSE if t != fpi)
    assert rows[domestic]["price_to_earnings"] is not None, (
        "the domestic control keeps its valuation block - the rule is scoped")


def test_the_transport_is_injectable_and_only_the_live_one_needs_the_network(tmp_path):
    """The stub proves the pipeline; the live SEC fetch is the networked half."""
    live = sec_xbrl_transport()
    assert callable(live), "the live transport exists as a callable"
    assert SEC_REQUESTS_PER_SECOND == 10.0, "paced to SEC's published ceiling"
    stub = Transport()
    build = build_panel(DATES, UNIVERSE, transport=stub, cache_dir=str(tmp_path))
    assert build["coverage"]["names_present"] == len(UNIVERSE)
    assert stub.calls == len(DATES)
    # the pipeline is exercised end to end with no network at all
    report = evaluate_panel(load_panel_series(DATES, UNIVERSE, cache_dir=str(tmp_path)),
                            dates=DATES)
    assert report["panel"]["n_names"] == len(UNIVERSE)


def test_the_technical_leg_uses_the_runs_own_component_assembly(tmp_path, monkeypatch):
    """One implementation: the panel substitutes the bar source, not the engine."""
    import tradingagents.agents.utils.analysis_tools as at

    n = 320
    long_dates = [f"2025-{1 + i // 28:02d}-{1 + i % 28:02d}" for i in range(n)]
    series = {t: _bars(long_dates, drift=0.0005 * i, seed=10 + i, noise=0.012)
              for i, t in enumerate(["AAA", "BBB", "SPY"])}
    provider = PriceProvider(loader=lambda t: series.get(t, {}))
    original = at._ohlcv
    rows = technical_rows_asof(["AAA", "BBB"], long_dates[-1], provider)
    assert at._ohlcv is original, "the run's bar source is restored"
    assert set(rows) == {"AAA", "BBB"}
    assert len(rows["AAA"]) >= 25, "the real producers measure most components"
    assert "adx" in rows["AAA"] and "rsi" in rows["AAA"]
    assert "breadth" not in str(rows), "market-wide breadth needs a panel, not a name"
    # and every value is a measurement, not a neutral 50
    from tradingagents.strategies.technical_score import COMPONENTS

    assert all(k in COMPONENTS for k in rows["AAA"])


def test_the_default_price_loader_does_not_recurse_into_the_bar_patch(monkeypatch):
    """The live-run defect: the provider must capture the REAL `_ohlcv`.

    `technical_rows_asof` rebinds `analysis_tools._ohlcv` to read bars from the
    provider. A default-loader provider that looked `_ohlcv` up at call time
    would find that patch and recurse, and every name would come back empty -
    which is exactly what the first live run produced (0 names of 150).
    """
    import tradingagents.agents.utils.analysis_tools as at

    n = 320
    long_dates = [f"2025-{1 + i // 28:02d}-{1 + i % 28:02d}" for i in range(n)]
    series = {t: _bars(long_dates, drift=0.0005 * i, seed=20 + i, noise=0.012)
              for i, t in enumerate(["AAA", "BBB", "SPY"])}
    monkeypatch.setattr(at, "_ohlcv", lambda ticker, days=320: series.get(ticker, {}))
    stub = at._ohlcv
    provider = PriceProvider()  # the default loader: the captured real function
    assert provider._loader is stub, "the loader is captured at construction"
    rows = technical_rows_asof(["AAA", "BBB"], long_dates[-1], provider)
    assert set(rows) == {"AAA", "BBB"}, "the default loader must not recurse"
    assert len(rows["AAA"]) >= 25
    assert at._ohlcv is stub, "the run's bar source is restored after the call"


def test_write_and_read_panel_round_trips_and_rejects_a_corrupt_file(tmp_path):
    path = panel_path(str(tmp_path), DATES[0])
    write_panel(path, {"msft": {"rsi": 55.0}}, {"fetched_at": "2026-09-18T00:00:00Z"})
    rows, meta = read_panel(path)
    assert rows == {"MSFT": {"rsi": 55.0}}, "tickers are normalised on write"
    assert meta["fetched_at"].startswith("2026-09-18")
    Path(path).write_text("{not json", encoding="utf-8")
    assert read_panel(path) is None, "a corrupt cache is re-fetched, never read as empty"


# --------------------------------------------------------------------------
# The rendered block, on the real report shape
# --------------------------------------------------------------------------


def test_the_rendered_block_carries_the_cost_and_coverage_line(tmp_path):
    build = build_panel([DATES[0]], UNIVERSE, transport=Transport(), cache_dir=str(tmp_path))
    report = evaluate_panel(load_panel_series([DATES[0]], UNIVERSE, cache_dir=str(tmp_path)),
                            dates=[DATES[0]])
    text = render_text(report, build)
    assert "API call(s)" in text and "cache hit(s)" in text
    assert "coverage:" in text and "label:" in text
    assert report["panel"]["status"] in text
    assert "weight vector: NONE" in text, "below the floors, the line says so"
