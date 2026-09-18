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
(g) the transport is injectable - the live EODHD fetch is the one thing that
    cannot be verified here (the Extended Fundamentals plan is support-gated).

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
    BULK_REQUEST_CALLS,
    CHUNK_SIZE,
    META_KEY,
    REDUNDANT_ABS_CORR,
    STATUS_ADVISORY,
    STATUS_RESEARCH_ONLY,
    BulkResult,
    PriceProvider,
    build_panel,
    canonical_fin_from_bulk,
    engine_registry,
    engine_weight_vector,
    estimate_cost,
    evaluate_panel,
    load_panel_series,
    multiple_testing,
    panel_path,
    read_panel,
    render_text,
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
    """A stub transport: deterministic rows plus its own call counter."""

    def __init__(self, factor_seed: int = 3):
        self.calls = 0
        self.api_calls = 0
        self.requested: list[str] = []
        self._rng = random.Random(factor_seed)
        self._rows = {
            t: {"fcf_yield": round(self._rng.gauss(0, 1), 4),
                "earnings_yield": round(self._rng.gauss(0, 1), 4)}
            for t in UNIVERSE
        }

    def _row(self, ticker: str) -> dict:
        # any symbol gets a row, so a larger universe is a real fetch, not gaps
        if ticker not in self._rows:
            self._rows[ticker] = {
                "fcf_yield": round(self._rng.gauss(0, 1), 4),
                "earnings_yield": round(self._rng.gauss(0, 1), 4),
            }
        return dict(self._rows[ticker])

    def __call__(self, chunk, date):
        self.calls += 1
        self.requested.extend(chunk)
        self.api_calls += BULK_REQUEST_CALLS + len(chunk)
        return BulkResult(
            rows={t: self._row(t) for t in chunk},
            requests=1,
            api_calls=BULK_REQUEST_CALLS + len(chunk),
            symbols_requested=len(chunk),
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
    assert build["cost"]["api_calls"] == BULK_REQUEST_CALLS * 3 + 1100
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


def test_the_universe_is_chunked_to_the_vendor_cap(tmp_path):
    transport = Transport()
    big = [f"T{i:04d}" for i in range(1100)]
    build_panel([DATES[0]], big, transport=transport, cache_dir=str(tmp_path))
    assert len(transport.requested) == 1100
    assert transport.calls == 3, "500-symbol cap => 500 + 500 + 100"
    est = estimate_cost(1100)
    assert est == {
        "source": "bulk fundamentals (EODHD Extended Fundamentals)",
        "symbols": 1100,
        "chunk_size": CHUNK_SIZE,
        "chunks": 3,
        "api_calls": 100 * 3 + 1100,
        "model": est["model"],
    }
    assert [len(c) for c in split_chunks([f"X{i}" for i in range(1100)])] == [500, 500, 100]
    # the estimate is what the run actually spends
    assert build_panel([DATES[1]], big, transport=Transport(),
                       cache_dir=str(tmp_path))["cost"]["api_calls"] == est["api_calls"]


def test_an_empty_fetch_is_not_cached_as_a_panel(tmp_path):
    class _Empty(Transport):
        def __call__(self, chunk, date):
            self.calls += 1
            return BulkResult(rows={}, requests=1, api_calls=BULK_REQUEST_CALLS,
                              symbols_requested=len(chunk))

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
# (g) the vendor leg: injectable transport, one honest mapping
# --------------------------------------------------------------------------


def test_the_vendor_payload_maps_to_canonical_financials_with_no_fabrication():
    payload = {
        "General": {"Sector": "Technology"},
        "Highlights": {"MarketCapitalization": 3_000_000_000, "SharesOutstanding": 100_000_000},
        "Financials": {
            "Income_Statement": {"yearly": {
                "2024-06-30": {"totalRevenue": 900.0, "netIncome": 90.0},
                "2025-06-30": {"totalRevenue": 1000.0, "netIncome": 100.0},
            }},
            "Balance_Sheet": {"yearly": {
                "0": {"totalAssets": 2000.0, "totalLiabilities": 1200.0,
                      "totalStockholderEquity": 800.0, "totalCurrentAssets": 700.0,
                      "totalCurrentLiabilities": 400.0, "inventory": 100.0,
                      "cashAndEquivalents": 150.0, "longTermDebtTotal": 500.0},
            }},
            "Cash_Flow": {"yearly": {
                "0": {"totalCashFromOperatingActivities": 200.0,
                      "capitalExpenditures": -50.0},
            }},
        },
    }
    fin = canonical_fin_from_bulk(payload)
    assert fin["revenue"] == {"current": 1000.0, "prior": 900.0}, "current/prior pairs"
    assert fin["net_income"]["current"] == 100.0
    assert fin["capex"]["current"] == 50.0, "capex is a positive magnitude for compute_ratios"
    assert fin["free_cash_flow"]["current"] == 150.0, "FCF from OCF - capex, not a proxy"
    assert fin["market_cap"] == 3_000_000_000
    assert fin["sector"] == "Technology"
    assert "ebitda" not in fin, "an absent field is absent, never 0"
    assert canonical_fin_from_bulk({}) == {}


def test_the_transport_is_injectable_and_only_the_live_one_is_unverified(tmp_path):
    """The stub proves the pipeline; the EODHD fetch needs the gated vendor plan."""
    from scripts.score_panel import eodhd_bulk_transport

    live = eodhd_bulk_transport()
    assert callable(live), "the live transport exists as a callable"
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
