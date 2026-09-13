"""Hermetic tests for the S8 score-evaluation rows.

Covers ``strategies/alpha_health.py::score_evaluation_rows`` (rank IC / IC IR,
rank-bucketed decile means + monotonicity, coverage, rank-autocorrelation
stability) and its consumer ``scripts/strategy_quality_report.py`` behind the
``enable_score_eval_rows`` gate.

Offline and deterministic: every panel is synthetic and the report's vendor
chain is monkeypatched - no live data is read.
"""

from __future__ import annotations

import json

from tradingagents.strategies.alpha_health import score_evaluation_rows

# --------------------------------------------------------------------------
# fixtures
# --------------------------------------------------------------------------


def _dates(n: int) -> list[str]:
    return [f"2026-01-{d:02d}" for d in range(1, n + 1)]


def _drift_prices(names, drifts, n_dates: int, holding: int) -> dict:
    """A price path per name with a constant per-name daily drift."""
    return {
        t: [100.0 * (1.0 + drifts[t]) ** i for i in range(n_dates + holding)]
        for t in names
    }


def _monotone_panel(n_dates=8, holding=1, n_buckets=5, missing=None):
    """10 names whose forward returns increase with a non-uniform score.

    The score gaps (1..9, then 100) are deliberately wide so rank bucketing
    and fixed-width bucketing disagree: rank bucketing fills every bucket and
    the means increase; fixed-width leaves the middle buckets empty.
    """
    names = [f"N{k}" for k in range(10)]
    drifts = {t: 0.01 * (k + 1) for k, t in enumerate(names)}
    scores = [1, 2, 3, 4, 5, 6, 7, 8, 9, 100]
    per_date = dict(zip(names, scores, strict=True))
    if missing is not None:
        per_date.pop(missing, None)  # a bar exists, but the score is missing
    scores_by_date = {d: dict(per_date) for d in _dates(n_dates)}
    prices = _drift_prices(names, drifts, n_dates, holding)
    return scores_by_date, prices, names, scores


# --------------------------------------------------------------------------
# perfect rank transform -> monotone deciles + IC ~= 1
# --------------------------------------------------------------------------


def test_perfect_rank_score_has_ic_one_and_monotone_deciles():
    scores_by_date, prices, _names, _scores = _monotone_panel()
    out = score_evaluation_rows(scores_by_date, prices, holding=1, n_buckets=5)

    ic = out["ic"]
    assert ic["available"] is True
    assert ic["n"] == 8
    assert ic["holding"] == 1
    assert ic["mean_rank_ic"] >= 0.99
    assert ic["ic_ir"] is not None

    dec = out["deciles"]
    assert dec["available"] is True
    assert dec["n"] == 80  # 8 usable periods x 10 names
    assert dec["buckets_filled"] == 5
    assert dec["monotonicity"] >= 0.999
    assert dec["monotone"] is True
    means = dec["bucket_means"]
    assert all(means[k] < means[k + 1] for k in range(len(means) - 1))


def test_basis_names_dsr_pbo_and_not_a_verdict():
    scores_by_date, prices, _n, _s = _monotone_panel()
    out = score_evaluation_rows(scores_by_date, prices, holding=1, n_buckets=5)
    assert "DSR/PBO" in out["basis"]
    assert "never a standalone verdict" in out["basis"]


# --------------------------------------------------------------------------
# shuffled / reversed score -> not monotone, IC not ~= 1
# --------------------------------------------------------------------------


def test_shuffled_score_is_not_monotone_and_ic_not_one():
    scores_by_date, prices, names, scores = _monotone_panel()
    shuffled = dict(zip(names, list(reversed(scores)), strict=True))
    scores_by_date = {d: dict(shuffled) for d in scores_by_date}
    out = score_evaluation_rows(scores_by_date, prices, holding=1, n_buckets=5)

    ic = out["ic"]
    assert ic["available"] is True
    assert ic["mean_rank_ic"] <= 0.5
    assert out["deciles"]["monotonicity"] <= 0.5
    assert out["deciles"]["monotone"] is False


# --------------------------------------------------------------------------
# coverage: a name with a bar but no score counts against coverage
# --------------------------------------------------------------------------


def test_coverage_counts_a_deliberately_missing_name():
    scores_by_date, prices, _names, _scores = _monotone_panel(
        n_dates=8, holding=1, missing="N9"
    )
    out = score_evaluation_rows(scores_by_date, prices, holding=1, n_buckets=5)

    cov = out["coverage"]
    assert cov["available"] is True
    assert cov["universe"] == 10 * 8  # ten priced names over eight dates
    assert cov["scored"] == 9 * 8  # N9 is priced but never scored
    assert abs(cov["ratio"] - 0.9) < 1e-12
    assert cov["per_date"]["2026-01-01"] == {"scored": 9, "universe": 10}


# --------------------------------------------------------------------------
# short panel -> every row unavailable with its count
# --------------------------------------------------------------------------


def test_short_panel_returns_unavailable_with_the_count():
    names = [f"N{k}" for k in range(6)]
    drifts = {t: 0.01 * (k + 1) for k, t in enumerate(names)}
    scores_by_date = {d: dict(zip(names, range(6), strict=True)) for d in _dates(3)}
    prices = _drift_prices(names, drifts, 3, 1)

    out = score_evaluation_rows(scores_by_date, prices, holding=1, n_buckets=3)
    assert out["n_dates"] == 3
    for row in ("ic", "deciles", "coverage", "stability"):
        assert out[row]["available"] is False
        assert out[row]["reason"]
    assert out["ic"]["n"] == 3  # 3 dates with a full 1-day forward path
    assert out["stability"]["n"] == 2  # 2 consecutive snapshot pairs


def test_min_obs_floor_boundary():
    names = [f"N{k}" for k in range(6)]
    drifts = {t: 0.01 * (k + 1) for k, t in enumerate(names)}
    scores_by_date = {d: dict(zip(names, range(6), strict=True)) for d in _dates(4)}
    prices = _drift_prices(names, drifts, 4, 1)

    strict = score_evaluation_rows(scores_by_date, prices, holding=1, n_buckets=3, min_obs=5)
    assert strict["ic"]["available"] is False
    assert strict["ic"]["n"] == 4

    relaxed = score_evaluation_rows(scores_by_date, prices, holding=1, n_buckets=3, min_obs=3)
    assert relaxed["ic"]["available"] is True
    assert relaxed["ic"]["n"] == 4


def test_empty_panel_degrades_without_fabricating():
    out = score_evaluation_rows({}, {}, holding=5)
    assert out["n_dates"] == 0
    assert out["universe_n"] == 0
    for row in ("ic", "deciles", "coverage", "stability"):
        assert out[row]["available"] is False
        assert out[row]["n"] == 0


# --------------------------------------------------------------------------
# report consumer (scripts/strategy_quality_report.py)
# --------------------------------------------------------------------------


def test_report_gate_off_omits_score_eval(tmp_path, monkeypatch):
    import scripts.strategy_quality_report as sqr
    import tradingagents.dataflows.config as cfgmod

    monkeypatch.setattr(cfgmod, "get_config", lambda: {"enable_score_eval_rows": False})
    out = sqr.build_report(str(tmp_path))
    assert "score_eval" not in out


def test_report_gate_on_without_ledger_is_unavailable(tmp_path, monkeypatch):
    import scripts.strategy_quality_report as sqr
    import tradingagents.dataflows.config as cfgmod

    monkeypatch.setattr(cfgmod, "get_config", lambda: {"enable_score_eval_rows": True})
    out = sqr.build_report(str(tmp_path))
    assert out["score_eval"]["available"] is False
    assert out["score_eval"]["n"] == 0


def test_score_eval_block_builds_panel_from_alpha_ledger(tmp_path, monkeypatch):
    import scripts.strategy_quality_report as sqr
    import tradingagents.agents.utils.analysis_tools as analysis_tools

    dates = _dates(12)
    ratings = ["BUY", "OVERWEIGHT", "HOLD", "UNDERWEIGHT", "SELL"]
    rows = [
        {"ticker": f"T{k}", "effective_date": d, "rating": r}
        for d in dates
        for k, r in enumerate(ratings)
    ]
    (tmp_path / "alpha_ledger.jsonl").write_text(
        "\n".join(json.dumps(r) for r in rows) + "\n", encoding="utf-8"
    )

    def fake_ohlcv(ticker, days=320):
        k = int(ticker[1:])
        drift = 0.01 * (len(ratings) - k)  # BUY (k=0) drifts most
        closes = [100.0 * (1.0 + drift) ** i for i in range(len(dates))]
        return {"dates": list(dates), "closes": closes}

    monkeypatch.setattr(analysis_tools, "_ohlcv", fake_ohlcv)
    block = sqr._score_eval_block(str(tmp_path))

    assert block["ic"]["available"] is True
    assert block["ic"]["mean_rank_ic"] >= 0.99
    assert block["coverage"]["ratio"] == 1.0
    # five names over a 10-bucket default fill five buckets, so no monotonicity
    # claim is made - the row is still emitted with its counts.
    assert block["deciles"]["available"] is True
    assert block["deciles"]["buckets_filled"] == 5
    assert block["deciles"]["monotonicity"] is None
    assert block["stability"]["available"] is True
