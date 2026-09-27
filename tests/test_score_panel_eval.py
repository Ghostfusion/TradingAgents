"""PLAN-4 - the evaluation CLI over a cached WP-10 panel.

Covers `docs/scores/IMPLEMENTATION_PLAN.md` section 7 (WP-10, PLAN-4) and
`docs/scores/MASTER_PLAN.md` Phase 3: the script prints the row set the layer
already produces - IC, rank IC, ICIR, decile spread, monotonicity, turnover,
persistence, the OOS split, the redundancy block, the sector/regime robustness
splits and the technical category matrix - and a withheld split carries its
reason rather than a number.

Offline and deterministic: the cache is a synthetic panel written to ``tmp_path``
and the CLI fetches nothing (a cache read makes zero network calls).
"""

from __future__ import annotations

import json
import math
import random

import pytest

from scripts.score_panel import (
    STATUS_ADVISORY,
    panel_path,
    write_panel,
)
from scripts.score_panel_eval import evaluate_cached_panel, main

pytestmark = pytest.mark.timeout(180)

DATES = [f"2026-09-{d:02d}" for d in range(1, 26)]
UNIVERSE = [f"T{i:03d}" for i in range(120)]
NOISE_METRICS = ("earnings_yield", "price_to_earnings", "adx", "roc20")


def _seed_cache(cache_dir: str) -> None:
    """Write one synthetic planted panel file per date (no transport, no fetch)."""
    rng = random.Random(7)
    truth = {t: rng.gauss(0.0, 1.0) for t in UNIVERSE}
    noise = {t: {m: [rng.gauss(0.0, 1.0) for _ in DATES] for m in NOISE_METRICS}
             for t in UNIVERSE}
    jitter = {t: [rng.gauss(0.0, 0.004) for _ in DATES] for t in UNIVERSE}
    for i, date in enumerate(DATES):
        rows: dict = {}
        for t in UNIVERSE:
            row = {m: noise[t][m][i] for m in NOISE_METRICS}
            row["fcf_yield"] = 0.05 * math.exp(0.3 * truth[t])
            row["close"] = round(50.0 * math.exp(0.004 * truth[t] * i + jitter[t][i]), 6)
            rows[t] = row
        write_panel(panel_path(cache_dir, date), rows, {"fetched_at": "2026-09-26T00:00:00Z"})


def _sectors() -> dict:
    return {t: ["XLK", "XLF", "XLE"][i % 3] for i, t in enumerate(UNIVERSE)}


def _regimes() -> dict:
    return {d: ("bull" if i < 13 else "bear") for i, d in enumerate(DATES)}


def test_the_cached_fixture_reports_every_named_row_set(tmp_path):
    cache = str(tmp_path)
    _seed_cache(cache)
    report = evaluate_cached_panel(cache, DATES, UNIVERSE,
                                   sector_of=_sectors(), regime_of=_regimes())
    assert report is not None
    assert report["status"] == STATUS_ADVISORY

    row = report["factors"]["fcf_yield"]
    assert row["measured"] is True
    ic = row["rows"]["ic"]
    assert ic["mean_rank_ic"] is not None, "rank IC"
    assert ic["mean_pearson_ic"] is not None, "IC"
    assert ic["ic_ir"] is not None, "ICIR"
    dec = row["rows"]["deciles"]
    assert dec["spread"] is not None, "decile spread"
    assert dec["ordering"]["adjacent_pairs"] > 0, "monotonicity"
    assert row["rows"]["stability"]["persistence"] is not None, "persistence"
    assert row["rows"]["turnover"]["mean_turnover"] is not None, "turnover"
    assert row["multiple_testing"]["oos"]["label"], "the OOS split"
    assert "redundant_with" in row, "the redundancy block"

    assert report["redundancy"]["blocks"], "the two named redundancy blocks"
    sector = report["robustness"]["sector"]
    assert sector["status"] == STATUS_ADVISORY
    assert sector["factors"]["fcf_yield"]["XLK"]["available"] is True
    regime = report["robustness"]["regime"]
    assert regime["status"] == STATUS_ADVISORY
    assert regime["factors"]["fcf_yield"]["bear"]["mean_rank_ic"] is not None


def test_a_withheld_split_carries_its_reason_never_a_number(tmp_path):
    cache = str(tmp_path)
    _seed_cache(cache)
    thin = {t: ("XLK" if i < 3 else "XLF") for i, t in enumerate(UNIVERSE)}
    report = evaluate_cached_panel(cache, DATES, UNIVERSE, sector_of=thin)
    assert report is not None
    split = report["robustness"]["sector"]["factors"]["fcf_yield"]
    assert split["XLK"]["available"] is False
    assert split["XLK"]["mean_rank_ic"] is None
    assert "min_names" in split["XLK"]["reason"]
    assert split["XLF"]["available"] is True


def test_the_regime_split_needs_a_regime_series_and_says_so(tmp_path):
    cache = str(tmp_path)
    _seed_cache(cache)
    report = evaluate_cached_panel(cache, DATES, UNIVERSE)
    assert report is not None
    regime = report["robustness"]["regime"]
    assert regime["status"] == "UNMEASURED"
    assert "no date carries a regime label" in regime["reason"]
    assert regime["factors"] == {}


def test_no_cached_panel_returns_none_and_the_cli_exits_nonzero(tmp_path):
    empty = str(tmp_path / "empty")
    assert evaluate_cached_panel(empty, DATES, UNIVERSE) is None
    assert main(["--dates", DATES[0], "--cache-dir", empty]) == 1


def test_the_cli_prints_the_report_and_the_json_form(tmp_path, capsys):
    cache = str(tmp_path)
    _seed_cache(cache)
    dates_arg = ",".join(DATES)
    code = main(["--dates", dates_arg, "--cache-dir", cache, "--json"])
    assert code == 0
    payload = json.loads(capsys.readouterr().out)
    assert "robustness" in payload and "technical_categories" in payload
    assert payload["factors"]["fcf_yield"]["rows"]["ic"]["mean_rank_ic"] is not None

    code = main(["--dates", dates_arg, "--cache-dir", cache])
    assert code == 0
    text = capsys.readouterr().out
    assert "## Factors" in text and "## Robustness splits (sector / regime)" in text
    assert "## Technical category correlations (TECH-24)" in text
