"""H6 - the three-way materiality verdict and the vocabulary's reach.

``docs/paper_survey_26/implementation_plan_research_honesty_gates.md`` §1 ``### H6``.

The load-bearing property: a non-significant result is *unresolved*, not
evidence of no edge. An interval that straddles the threshold is INCONCLUSIVE
and must never collapse into REFUTED - which is what
``test_straddling_interval_is_inconclusive`` fails on by name when the collapse
is introduced.
"""

from __future__ import annotations

from tradingagents.agents.utils.report_verifier import (
    ReportVerification,
    report_materiality_verdict,
)
from tradingagents.strategies.evaluate import (
    benchmark_table,
    family_materiality,
    materiality_verdict,
)

DELTA = 0.20


def _gate(monkeypatch, on: bool) -> None:
    """Flip ``enable_materiality_verdict`` at the config accessor the read uses."""
    monkeypatch.setattr(
        "tradingagents.dataflows.config.get_config",
        lambda: {"enable_materiality_verdict": on},
    )


def test_straddling_interval_is_inconclusive():
    """A straddling interval is INCONCLUSIVE, not REFUTED (underpowered != null).

    The point estimate sits BELOW the threshold in the middle case: the test
    cannot tell which side the effect is on, so the honest label is unresolved.
    Collapsing that into REFUTED makes the middle assertion fail by name.
    """
    # Interval clears the threshold: supported.
    assert materiality_verdict(0.31, 0.25, 0.40, DELTA) == "SUPPORTED"
    # Interval lies entirely below it: refuted - the ONLY refuting case.
    assert materiality_verdict(0.10, 0.02, 0.15, DELTA) == "REFUTED"
    # Straddling the threshold: unresolved, never refuted. Both a point estimate
    # above the bar and one below it land here.
    assert materiality_verdict(0.22, 0.05, 0.41, DELTA) == "INCONCLUSIVE"
    assert materiality_verdict(0.19, 0.18, 0.24, DELTA) == "INCONCLUSIVE"
    # A missing interval is not a verdict, and is never reported as REFUTED.
    assert materiality_verdict(float("nan"), 0.1, 0.2, DELTA) == "unavailable"


def test_verifier_accepts_and_emits_inconclusive():
    """The three-way vocabulary reaches the verifier's verdict field."""
    # The field accepts the value and carries it through serialization.
    model = ReportVerification(report="market", overall="FLAG", verdict="INCONCLUSIVE")
    assert model.model_dump()["verdict"] == "INCONCLUSIVE"
    assert ReportVerification(report="market", overall="PASS").verdict == "UNKNOWN"

    # The producer emits INCONCLUSIVE for a stem that is unproven, not
    # disproven: one grounded claim among claims no leaf could settle is
    # underpowered, and an UNSUPPORTED claim is never refutation.
    unproven = [
        {"claim": "revenue grew 12%", "status": "GROUNDED", "reason": "leaf"},
        {"claim": "margins held", "status": "UNSUPPORTED", "reason": "no leaf"},
        {"claim": "guidance was raised", "status": "UNSUPPORTED", "reason": "no leaf"},
        {"claim": "backlog is firm", "status": "UNSUPPORTED", "reason": "no leaf"},
    ]
    assert report_materiality_verdict(unproven) == "INCONCLUSIVE"

    # A contradicted claim is the only thing that refutes the stem.
    refuted = [dict(c) for c in unproven]
    refuted[1]["status"] = "CONTRADICTED"
    assert report_materiality_verdict(refuted) == "REFUTED"
    assert report_materiality_verdict([]) == "UNKNOWN"


def test_exposure_matched_arm_replays_when_in():
    """The benchmark is replayed on the strategy's own in-market bars.

    The arm must differ from the plain benchmark (it is not a copy): only the
    bars the strategy held keep the benchmark's return, the rest are cash.
    """
    benchmark = [0.01, -0.02, 0.03, -0.01, 0.005, 0.02]
    strategy = [0.0] * len(benchmark)
    exposure = [1, 0, 1, 0, 0, 1]
    table = benchmark_table(strategy, benchmark, exposure=exposure)
    rows = {row["name"]: row for row in table["rows"]}
    assert table["window"] == len(benchmark)
    assert "exposure_matched" in rows
    # 1.01 * 1.03 * 1.02 - 1 compounded over the in-market bars only.
    assert rows["exposure_matched"]["total_return"] == 0.0611
    assert rows["benchmark"]["total_return"] != rows["exposure_matched"]["total_return"]

    # No exposure -> no arm (the default path is unchanged), and an unaligned
    # exposure is dropped rather than misaligned onto the wrong bars.
    assert "exposure_matched" not in {
        row["name"] for row in benchmark_table(strategy, benchmark)["rows"]
    }
    short = benchmark_table(strategy, benchmark, exposure=[1, 0])["rows"]
    assert "exposure_matched" not in {row["name"] for row in short}


def test_family_fdr_classifies_without_refuting_on_power(monkeypatch):
    """The family FDR gates on the threshold and never refutes a strong read.

    A candidate whose grounding clears the bar and survives the correction is
    SUPPORTED; a flat candidate whose interval lies entirely below the bar is
    REFUTED; and the gate itself decides whether the instrument runs at all.
    """
    # Gate off (the default): the instrument is not run.
    _gate(monkeypatch, on=False)
    benchmark = [0.0] * 40
    strong = [0.02, 0.03] * 20
    flat = [0.0, 0.001] * 20
    assert family_materiality({"strong": strong, "flat": flat}, benchmark,
                              n_boot=50) is None

    _gate(monkeypatch, on=True)
    family = family_materiality({"strong": strong, "flat": flat}, benchmark,
                                n_boot=200, seed=0)
    assert family is not None
    assert family["surviving"] >= 1
    verdicts = {row["name"]: row["verdict"] for row in family["candidates"]}
    assert verdicts["strong"] == "SUPPORTED"
    assert verdicts["flat"] == "REFUTED"
    # A single candidate cannot form a family.
    assert family_materiality({"only": strong}, benchmark, n_boot=50) is None
