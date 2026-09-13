"""Round-3 S3: composite quality score (winsorised z -> percentile 0-100).

The score is specified as a transform (plan §2 S3): per metric winsorise
0.01/0.99 -> cross-sectional z -> apply the metric's direction sign -> mean over
the present metrics -> tie-aware percentile x100 in the peer set. Because the
last step is rank-based, winsorising cannot reorder names; it changes the
reported ``z`` (an outlier is clipped to the 0.99 quantile before
standardisation) and can only create ties at the top. That is asserted at the
``z`` level below - the mutation "skip winsorising" is caught there.
"""

from __future__ import annotations

from tradingagents.strategies.cross_section import cross_sectional_z, winsorize
from tradingagents.strategies.decision_guardrail import SCORE_BANDS
from tradingagents.strategies.factors import (
    QUALITY_BANDS,
    quality_band,
    quality_composite,
)

DIRECTIONS = {"f": 1, "m": -1, "z": 1}


def _rise_panel(n: int = 10, metrics=("f", "m", "z")) -> dict:
    """N0..N{n-1} where every metric agrees on the ordering (N0 worst, N9 best).

    ``f`` and ``z`` rise with the index (direction +1); ``m`` falls (direction
    -1, lower is better), so all three point the same way.
    """
    panel: dict = {}
    for i in range(n):
        row: dict = {}
        if "f" in metrics:
            row["f"] = float(i + 1)
        if "m" in metrics:
            row["m"] = float(n - i)
        if "z" in metrics:
            row["z"] = float((i + 1) * (i + 1))
        panel[f"N{i}"] = row
    return panel


def _order(result: dict) -> list[float]:
    return [result["scores"][f"N{i}"] for i in range(10)]


def test_best_and_worst_names_rank_100_and_0() -> None:
    res = quality_composite(_rise_panel(), directions=DIRECTIONS, min_coverage=3)
    assert sorted(res["scores"]) == [f"N{i}" for i in range(10)]
    assert res["scores"]["N0"] == 0.0
    assert res["scores"]["N9"] == 100.0
    assert res["peer_n"] == 10
    assert res["metrics_used"] == ["f", "m", "z"]


def test_scores_are_monotone_in_the_ordering() -> None:
    res = quality_composite(_rise_panel(), directions=DIRECTIONS, min_coverage=3)
    scores = _order(res)
    assert all(a < b for a, b in zip(scores, scores[1:], strict=False))


def test_peer_set_below_the_floor_is_unavailable() -> None:
    res = quality_composite(_rise_panel(n=5), directions=DIRECTIONS, min_coverage=3)
    assert res["scores"] == {}
    assert "unavailable" in res
    assert res["peer_n"] == 5
    assert "5 < 8" in res["unavailable"]


def test_metric_without_a_declared_direction_is_dropped() -> None:
    panel = _rise_panel()
    for i, row in enumerate(panel.values()):
        row["undirected"] = float(i + 1)
    res = quality_composite(panel, directions=DIRECTIONS, min_coverage=3)
    assert res["metrics_dropped"]["undirected"] == "no declared direction"
    assert "undirected" not in res["metrics_used"]


def test_metric_present_for_too_few_names_is_dropped_with_its_count() -> None:
    panel = _rise_panel()
    panel["N0"]["rare"] = 1.0
    panel["N1"]["rare"] = 2.0
    res = quality_composite(
        panel, directions={**DIRECTIONS, "rare": 1}, min_coverage=3
    )
    assert "rare" not in res["metrics_used"]
    assert "2 of 10" in res["metrics_dropped"]["rare"]


def test_name_below_the_coverage_floor_is_withheld_with_the_count() -> None:
    panel = _rise_panel()
    panel["N5"] = {"f": 6.0}
    res = quality_composite(panel, directions=DIRECTIONS, min_coverage=3)
    assert "N5" not in res["scores"]
    assert res["coverage"]["N5"] == {"n": 1, "of": 3, "metrics": ["f"]}
    assert "1 of 3" in res["withheld"]["N5"]
    assert len(res["scores"]) == 9


def test_a_missing_metric_is_renormalised_over_the_present_metrics() -> None:
    """A middle name missing one metric keeps its place (2/3 of its z would not)."""
    panel = _rise_panel()
    panel["N5"] = {"f": 6.0, "m": 5.0}
    res = quality_composite(panel, directions=DIRECTIONS, min_coverage=2)
    assert "N5" in res["scores"]
    assert res["coverage"]["N5"]["n"] == 2
    assert res["coverage"]["N5"]["of"] == 3
    scores = [res["scores"][f"N{i}"] for i in range(10)]
    assert all(a < b for a, b in zip(scores, scores[1:], strict=False))
    # The documented transform: mean of the *present* metrics' signed z.
    names = sorted(panel)

    def _signed(metric: str, direction: int) -> dict:
        col = [panel[t].get(metric) for t in names]
        z = cross_sectional_z(winsorize(col, 0.01, 0.99))
        assert z is not None
        finite = [i for i, v in enumerate(col) if v is not None]
        sign = 1.0 if direction >= 0 else -1.0
        return {names[i]: sign * z["z"][k] for k, i in enumerate(finite)}

    zf, zm = _signed("f", 1), _signed("m", -1)
    assert res["z"]["N5"] == (zf["N5"] + zm["N5"]) / 2.0


def test_extreme_outlier_is_winsorised_before_standardising() -> None:
    panel = {f"N{i}": {"f": float(i + 1)} for i in range(12)}
    panel["OUT"] = {"f": 9000.0}
    res = quality_composite(panel, directions={"f": 1}, min_coverage=1)
    names = sorted(panel)
    col = [panel[t]["f"] for t in names]
    expected = cross_sectional_z(winsorize(col, 0.01, 0.99))
    assert expected is not None
    idx = names.index("OUT")
    assert res["z"]["OUT"] == expected["z"][idx]
    raw = cross_sectional_z(col)
    assert raw is not None and res["z"]["OUT"] < raw["z"][idx]


def test_direction_flips_a_lower_is_better_metric() -> None:
    panel = {f"N{i}": {"m": float(10 - i)} for i in range(10)}
    lower_better = quality_composite(panel, directions={"m": -1}, min_coverage=1)
    assert lower_better["scores"]["N9"] == 100.0  # m = 1.0, the lowest
    assert lower_better["scores"]["N0"] == 0.0
    higher_better = quality_composite(panel, directions={"m": 1}, min_coverage=1)
    assert higher_better["scores"]["N0"] == 100.0
    assert higher_better["scores"]["N9"] == 0.0


def test_industry_neutral_is_an_opt_in_switch_and_is_printed() -> None:
    panel = _rise_panel()
    sectors = {f"N{i}": ("A" if i < 5 else "B") for i in range(10)}
    raw = quality_composite(panel, directions=DIRECTIONS, min_coverage=3)
    neutral = quality_composite(
        panel,
        directions=DIRECTIONS,
        min_coverage=3,
        sector_map=sectors,
        industry_neutral=True,
    )
    assert raw["industry_neutral"] is False
    assert "raw cross-sectional" in raw["basis"]
    assert neutral["industry_neutral"] is True
    assert "industry-neutral" in neutral["basis"]


def test_equal_weights_are_the_default_and_printed() -> None:
    res = quality_composite(_rise_panel(), directions=DIRECTIONS, min_coverage=3)
    assert "equal weights" in res["basis"]
    weighted = quality_composite(
        _rise_panel(),
        directions=DIRECTIONS,
        min_coverage=3,
        weights={"f": 3.0, "m": 1.0, "z": 1.0},
    )
    assert "weighted" in weighted["basis"]
    assert "3.0" in weighted["basis"]


def test_a_cross_section_that_yields_no_scored_name_withholds_everything() -> None:
    res = quality_composite(_rise_panel(), directions=DIRECTIONS, min_coverage=4)
    assert res["scores"] == {}
    assert len(res["withheld"]) == 10
    assert "3 of 3" in res["withheld"]["N0"]


def test_bands_are_the_quality_bands_not_the_decision_rating_bands() -> None:
    labels = {label for _, label in QUALITY_BANDS}
    assert quality_band(100) == "elite"
    assert quality_band(65) == "above-average"
    assert quality_band(55) == "sector median"
    assert quality_band(45) == "below-average"
    assert quality_band(30) == "poor"
    assert quality_band(10) == "distressed"
    assert quality_band(None) is None
    assert labels.isdisjoint({name for _, name in SCORE_BANDS})
