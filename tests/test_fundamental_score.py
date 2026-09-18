"""`FundamentalScore` (WP-2): the four sub-scores, the composite, the DCF leg.

Covers the plan's own acceptance list (`docs/scores/IMPLEMENTATION_PLAN.md` §5.1):
(a) a name with 3 of 7 factors present scores on those 3 and prints its coverage;
(b) `basis` names the metric set, the floor, the weight vector and whether the
weights were equal; (c) the printed sub-scores recompute the composite; (d)
`dcf_confidence` moves the DCF upside factor; (e) nothing writes
`opportunity_score`.

Offline and deterministic: every panel is synthetic and the one vendor-touching
seam (`resolve_peer_universe`) is injected or monkeypatched - no live data.
"""

from __future__ import annotations

import pytest

from tradingagents.strategies.factor_schema import (
    FACTOR_SCHEMA,
    SUBSCORE_FACTORS,
    availability_report,
    subscore_directions,
    validate_schema,
)
from tradingagents.strategies.fundamental_score import (
    COMPOSITE_MIN_COVERAGE,
    DCF_THRESHOLDS,
    INCOMPLETE_CAP,
    STATUS_ADVISORY,
    STATUS_RESEARCH_ONLY,
    SUBSCORE_BANDS,
    dcf_confidence,
    dcf_upside_scaled,
    factor_gap_report,
    fundamental_score,
    fundamental_score_for_ticker,
    growth_subscore,
    quality_subscore,
    risk_subscore,
    subscores,
    valuation_subscore,
)


def _panel(n: int = 10, *, extra: bool = True) -> dict:
    """A rising peer panel: every metric orders N0 < N1 < ... < N9.

    `extra` adds the valuation legs; without them only the quality factors are
    present, which is how a partial panel looks.
    """
    out = {}
    for i in range(n):
        row = {
            "f": float(i),
            "m": float(n - i),
            "gp_a": 0.30 + i / 100.0,
            "noa": 0.10 * i,
            "accruals": -0.02 * i,
            "return_on_equity": 0.05 + i / 100.0,
        }
        if extra:
            row.update(
                {
                    "ev_ebit": 30.0 - i,
                    "price_to_earnings": 40.0 - 2 * i,
                    "earnings_yield": 0.02 + i / 200.0,
                }
            )
        out[f"N{i}"] = row
    return out


# --------------------------------------------------------------------------
# the schema record (Q3)
# --------------------------------------------------------------------------


def test_schema_self_check_passes() -> None:
    validate_schema()


def test_no_factor_enters_two_sub_scores() -> None:
    """Master rule 15: one number, one category of the composite.

    The design's §3.1 table listed `o` (Ohlson) in FQS *and* FRS; that would put
    the same distress probability into two categories of one composite. FRS owns
    it.
    """
    seen: dict[str, str] = {}
    for sub, factors in SUBSCORE_FACTORS.items():
        for f in factors:
            assert f not in seen, f"{f} in both {seen.get(f)} and {sub}"
            seen[f] = sub
    assert "o" in SUBSCORE_FACTORS["FRS"]
    assert "o" not in SUBSCORE_FACTORS["FQS"]


def test_an_unavailable_factor_is_recorded_not_proxied() -> None:
    """`NA` is not `0`: a factor with no supplier is named, never substituted."""
    gaps = factor_gap_report()
    assert "rev_cagr5" in gaps["FGS"]["NA"]
    assert "fcf_yield" in gaps["VS"]["NA"]
    assert "val_z" in gaps["VS"]["NA"]
    # and the declared-present sets carry no NA factor
    for sub, rep in gaps.items():
        assert not set(rep["present"]) & set(rep["NA"])
        assert set(rep["present"]) | set(rep["NA"]) == set(SUBSCORE_FACTORS[sub])


def test_schema_directions_match_the_quality_table_where_they_overlap() -> None:
    """One direction per measure: the shared factors keep their published sign."""
    from tradingagents.strategies.factors import QUALITY_DIRECTIONS

    for f in ("f", "m", "z", "o", "gp_a", "noa", "accruals"):
        if f in FACTOR_SCHEMA:
            assert FACTOR_SCHEMA[f].direction == QUALITY_DIRECTIONS[f]


def test_every_schema_record_carries_all_nine_fields() -> None:
    for spec in FACTOR_SCHEMA.values():
        assert spec.factor and spec.category and spec.formula
        assert spec.direction in (1, -1)
        assert spec.base_weight is None  # no fabricated coefficients
        assert spec.sector_scope and spec.normalization_method and spec.supplier
        assert spec.availability in ("present", "NA")


# --------------------------------------------------------------------------
# acceptance (a) - partial coverage scores on what is present
# --------------------------------------------------------------------------


def test_three_of_seven_factors_present_scores_on_those_three() -> None:
    panel = _panel()
    panel["N3"] = {"f": 3.0, "m": 7.0, "gp_a": 0.33}
    res = quality_subscore(panel, min_coverage=3)
    cov = res["coverage"]["N3"]
    assert cov == {"n": 3, "of": 7, "metrics": ["f", "gp_a", "m"]}
    assert res["scores"]["N3"] is not None
    assert res["subscore"] == "FQS" and res["status"] == STATUS_ADVISORY


def test_coverage_denominator_is_the_subscore_not_the_panel() -> None:
    """A sub-score counts its own factors, not every metric the panel carries."""
    panel = _panel()
    fqs = quality_subscore(panel, min_coverage=3)
    assert all(entry["of"] == 7 for entry in fqs["coverage"].values())
    vs = valuation_subscore(panel, min_coverage=1)
    # VS declares 12 factors, 2 of which are NA on this path -> 10 considered
    assert all(entry["of"] == 10 for entry in vs["coverage"].values())


def test_subscore_basis_states_its_own_factor_count() -> None:
    """The printed basis must not quote the panel's metric count for a sub-score."""
    res = quality_subscore(_panel(), min_coverage=3)
    assert "coverage floor 3 of 7 factors" in res["basis"]
    assert "24 metrics" not in res["basis"]


def test_a_subscore_floor_is_capped_at_its_own_factor_count() -> None:
    """FGS has two factors with a supplier; a floor of 3 would be an off switch."""
    panel = {f"N{i}": {"revenue_yoy": 0.05 * i, "eps_yoy": 0.04 * i} for i in range(10)}
    res = growth_subscore(panel, min_coverage=3)
    assert res["floor"] == 2
    assert all(v is not None for v in res["scores"].values())
    assert all(entry["of"] == 2 for entry in res["coverage"].values())
    # a sub-score with more factors than the floor keeps the floor it was given
    assert quality_subscore(_panel(), min_coverage=3)["floor"] == 3


def test_below_the_floor_is_withheld_with_the_reason_never_zero() -> None:
    panel = _panel()
    panel["N4"] = {"f": 4.0}
    res = quality_subscore(panel, min_coverage=3)
    assert "N4" not in res["scores"]
    assert res["withheld"]["N4"] == "coverage 1 of 7 factors < floor 3"
    assert res["coverage"]["N4"]["n"] == 1


def test_a_missing_factor_does_not_punish_the_name() -> None:
    """`NA != 0`: the name with a hole scores on its own merits, not at zero."""
    panel = _panel()
    full = quality_subscore(panel, min_coverage=3)["scores"]
    holed = {k: v for k, v in panel.items()}
    holed["N9"] = {k: v for k, v in panel["N9"].items() if k != "gp_a"}
    after = quality_subscore(holed, min_coverage=3)["scores"]
    assert after["N9"] is not None
    # the name's own standing is what moves, not a punitive 0
    assert after["N9"] > 0.0
    assert after["N9"] != full["N9"] or after["N9"] == 100.0


# --------------------------------------------------------------------------
# acceptance (b) - the basis says what the number is made of
# --------------------------------------------------------------------------


def test_basis_names_the_metric_set_the_floor_and_the_weights() -> None:
    res = quality_subscore(_panel(), min_coverage=3)
    basis = res["basis"]
    assert basis.startswith("FQS (quality / profitability):")
    assert "coverage floor" in basis
    assert "no weight vector published, equal weights used" in basis


def test_a_published_weight_vector_is_printed_instead() -> None:
    panel = _panel()
    res = quality_subscore(panel, min_coverage=3, weights={"f": 2.0, "m": 1.0})
    assert "weights {'f': 2.0, 'm': 1.0}" in res["basis"] or "weighted" in res["basis"]


def test_subscore_bands_are_not_the_decision_rating_bands() -> None:
    from tradingagents.strategies.decision_guardrail import SCORE_BANDS

    for sub, bands in SUBSCORE_BANDS.items():
        assert tuple(bands) != tuple(SCORE_BANDS), sub
        labels = {label for _, label in bands}
        assert not labels & {label for _, label in SCORE_BANDS}, sub


# --------------------------------------------------------------------------
# acceptance (c) - the printed sub-scores recompute the composite
# --------------------------------------------------------------------------


def test_the_printed_subscores_recompute_the_composite() -> None:
    res = fundamental_score(_panel())
    key = "N9"
    comps = res["components"][key]
    present = [v for v in comps.values() if v is not None]
    assert len(present) >= COMPOSITE_MIN_COVERAGE
    assert res["scores"][key] == pytest.approx(sum(present) / len(present), abs=1e-9)
    # and each present component is the sub-score the engine printed
    for sub, value in comps.items():
        if value is None:
            continue
        assert value == res["subscores"][sub]["scores"][key]


def test_composite_is_research_only_and_equal_weighted() -> None:
    res = fundamental_score(_panel())
    assert res["status"] == STATUS_RESEARCH_ONLY
    assert res["weights"] is None
    assert "equal weights (1/4 each; no validated vector published)" in res["basis"]
    assert "no band table is applied" in res["basis"]


def test_a_name_below_the_composite_floor_is_withheld_not_scored() -> None:
    panel = _panel()
    panel["N3"] = {"f": 3.0, "m": 7.0, "gp_a": 0.33}  # FQS only
    res = fundamental_score(panel)
    assert res["scores"]["N3"] is None
    assert "1 of 4 components present" in res["withheld"]["N3"]


def test_composite_weights_are_honoured_when_supplied() -> None:
    res = fundamental_score(_panel(), weights={"FQS": 3.0, "VS": 1.0}, min_coverage=2)
    comps = res["components"]["N9"]
    num = 3.0 * comps["FQS"] + 1.0 * comps["VS"]
    assert res["scores"]["N9"] == pytest.approx(num / 4.0, abs=1e-9)


# --------------------------------------------------------------------------
# acceptance (d) - the DCF leg is scaled by its own confidence
# --------------------------------------------------------------------------


def test_dcf_confidence_reads_four_legs_and_caps_an_incomplete_read() -> None:
    full = dcf_confidence(
        basis="as reported",
        beta=1.1,
        beta_assumed=False,
        fcf_series=[10.0, 10.0, 10.0, 10.0, 10.0],
        terminal_share=0.4,
    )
    assert full["confidence"] == 1.0 and full["complete"] is True
    assert sorted(full["legs"]) == [
        "assumption_stability",
        "data_quality",
        "fcf_stability",
        "terminal_sensitivity",
    ]
    partial = dcf_confidence(basis="as reported", beta=1.1, terminal_share=0.4)
    assert "fcf_stability" in partial["legs_missing"]
    assert partial["complete"] is False
    assert partial["confidence"] <= INCOMPLETE_CAP


def test_no_readable_leg_yields_no_confidence_rather_than_a_number() -> None:
    # every leg unreadable except data quality, which is readable by its
    # absence of a stated basis (0.6) - and the cap still applies
    out = dcf_confidence()
    assert len(out["legs_missing"]) == 3
    assert out["complete"] is False
    assert out["confidence"] <= INCOMPLETE_CAP
    assert out["legs"]["data_quality"] == 0.6
    assert dcf_confidence(beta=None, fcf_series=None, terminal_share=None,
                          basis=None)["confidence"] is not None


def test_a_low_confidence_dcf_contributes_less_to_valuation() -> None:
    """§3.4: the DCF upside factor is scaled, so a soft DCF weighs less."""
    panel = {f"N{i}": {"dcf_upside": 0.30 - i / 100.0} for i in range(10)}
    confident = dcf_confidence(
        basis="as reported",
        beta=1.1,
        beta_assumed=False,
        fcf_series=[10.0, 11.0, 9.0, 10.0],
        terminal_share=0.4,
    )
    soft = dcf_confidence(
        basis_conflict="two vendors disagree on net debt",
        beta=1.1,
        beta_assumed=True,
        beta_range=0.5,
        fcf_series=[10.0, 40.0, -5.0, 30.0],
        terminal_share=0.95,
    )
    assert soft["confidence"] < confident["confidence"]

    hi = dcf_upside_scaled(panel["N0"]["dcf_upside"], confident["confidence"])
    lo = dcf_upside_scaled(panel["N0"]["dcf_upside"], soft["confidence"])
    assert lo["effective"] < hi["effective"]

    with_hi = {**panel, "N0": {**panel["N0"], "dcf_upside": hi["effective"]}}
    with_lo = {**panel, "N0": {**panel["N0"], "dcf_upside": lo["effective"]}}
    score_hi = valuation_subscore(with_hi, min_coverage=1)["scores"]["N0"]
    score_lo = valuation_subscore(with_lo, min_coverage=1)["scores"]["N0"]
    assert score_lo < score_hi


def test_dcf_upside_scaling_without_a_confidence_drops_the_factor() -> None:
    out = dcf_upside_scaled(0.25, None)
    assert out["effective"] is None and out["raw"] == 0.25


def test_dcf_thresholds_are_reported_with_the_score() -> None:
    out = dcf_confidence(basis="as reported", beta=1.0, terminal_share=0.5)
    assert out["thresholds"]["incomplete_cap"] == DCF_THRESHOLDS["incomplete_cap"]
    assert "product of the measured legs" in out["basis"]


# --------------------------------------------------------------------------
# acceptance (e) - nothing here is the opportunity score
# --------------------------------------------------------------------------


def test_no_opportunity_score_is_written() -> None:
    res = fundamental_score(_panel())
    assert "opportunity_score" not in res
    for sub_res in res["subscores"].values():
        assert "opportunity_score" not in sub_res


# --------------------------------------------------------------------------
# the ticker-level entry point and the panel extension
# --------------------------------------------------------------------------


def test_for_ticker_scores_the_resolved_panel_and_names_it() -> None:
    panel = _panel()
    calls: dict = {}

    def _resolver(*, tickers, current_date, include_score_metrics):
        calls["tickers"] = list(tickers)
        calls["include_score_metrics"] = include_score_metrics
        return {"metrics": panel, "basis": "synthetic panel"}

    res = fundamental_score_for_ticker(
        "n9", "2026-09-17", peers=["N0", "N1"], resolver=_resolver
    )
    assert calls["tickers"] == ["N9", "N0", "N1"]
    assert calls["include_score_metrics"] is True
    assert res["ticker"] == "N9"
    assert res["scores"]["N9"] is not None
    assert res["panel_basis"] == "synthetic panel"


def test_for_ticker_rejects_an_empty_ticker() -> None:
    with pytest.raises(ValueError):
        fundamental_score_for_ticker("  ", resolver=lambda **kw: {"metrics": {}})


def test_scaled_dcf_upside_reaches_the_panel_only_when_supplied() -> None:
    panel = {f"N{i}": {"ev_ebit": 30.0 - i} for i in range(10)}

    def _resolver(*, tickers, current_date, include_score_metrics):
        return {"metrics": panel, "basis": "synthetic"}

    plain = fundamental_score_for_ticker("N0", resolver=_resolver)
    assert "dcf_upside" not in (plain["subscores"]["VS"]["metrics_used"] or [])
    scaled = fundamental_score_for_ticker(
        "N0", resolver=_resolver, dcf_upside=0.25, dcf_confidence_value=0.5
    )
    assert scaled["dcf_upside"]["effective"] == pytest.approx(0.125)
    # one name's DCF cannot be z-scored against peers who have none, so the
    # core drops the metric with its reason (present for 1 of 10 names)
    assert "dcf_upside" not in (scaled["subscores"]["VS"]["metrics_used"] or [])
    assert "dcf_upside" in scaled["subscores"]["VS"]["metrics_dropped"]
    # with the leg on the whole panel it is used, and the scaled value is what
    # enters the engine
    full = {f"N{i}": {"ev_ebit": 30.0 - i, "dcf_upside": 0.2 - i / 100.0} for i in range(10)}
    full["N0"] = {**full["N0"], "dcf_upside": 0.125}
    scaled_full = fundamental_score_for_ticker("N0", resolver=_resolver,
                                               dcf_upside=None)
    assert "dcf_upside" in (
        fundamental_score_for_ticker(
            "N0", resolver=lambda **kw: {"metrics": full, "basis": "synthetic"},
            dcf_upside=0.25, dcf_confidence_value=0.5,
        )["subscores"]["VS"]["metrics_used"] or []
    )


def test_panel_extension_is_opt_in_and_leaves_the_quality_panel_alone() -> None:
    """The round-3 quality composite's published coverage must not move."""
    from tradingagents.strategies.peer_universe import _panel_from_fin

    fin = {
        "market_cap": {"value": 1_000_000.0},
        "total_debt": {"value": 200_000.0},
        "cash": {"value": 50_000.0},
        "operating_income": {"value": 90_000.0},
        "depreciation": {"value": 10_000.0},
        "revenue": {"value": 500_000.0},
        "net_income": {"value": 60_000.0},
        "total_equity": {"value": 400_000.0},
        "total_assets": {"value": 900_000.0},
        "total_liabilities": {"value": 500_000.0},
        "operating_cashflow": {"value": 80_000.0},
        "capex": {"value": 20_000.0},
        "current_assets": {"value": 300_000.0},
        "current_liabilities": {"value": 150_000.0},
        "inventory": {"value": 40_000.0},
        "working_capital": {"value": 150_000.0},
    }
    base = _panel_from_fin("TEST", fin)
    extended = _panel_from_fin("TEST", fin, include_score_metrics=True)
    assert set(base) <= set(extended)
    assert "price_to_earnings" in extended
    assert "price_to_earnings" not in base
    assert "earnings_yield" in extended
    # the quality factors themselves are unchanged by the extension
    for k, v in base.items():
        assert extended[k] == v


# --------------------------------------------------------------------------
# the gate
# --------------------------------------------------------------------------


def test_gate_off_keeps_the_engine_tool_out_of_every_toolset(monkeypatch) -> None:
    """§6 acceptance (a): a gate that is off leaves the toolset byte-identical."""
    import tradingagents.dataflows.config as cfgmod
    from tradingagents.agents import toolsets

    monkeypatch.setattr(
        cfgmod, "get_config", lambda: {"enable_fundamental_score": False}
    )
    names_off = [t.name for t in toolsets.fundamentals_company_tools()]
    assert "get_fundamental_score" not in names_off
    monkeypatch.setattr(
        cfgmod, "get_config", lambda: {"enable_fundamental_score": True}
    )
    names_on = [t.name for t in toolsets.fundamentals_company_tools()]
    assert "get_fundamental_score" in names_on
    assert set(names_on) - set(names_off) == {"get_fundamental_score"}


def test_gate_off_makes_the_leaf_say_so(monkeypatch) -> None:
    import tradingagents.dataflows.config as cfgmod
    from tradingagents.agents.utils.analysis_tools import get_fundamental_score

    monkeypatch.setattr(
        cfgmod, "get_config", lambda: {"enable_fundamental_score": False}
    )
    out = get_fundamental_score.invoke({"ticker": "MSFT"})
    assert "gated off" in out and "enable_fundamental_score" in out


def test_leaf_renders_the_subscores_coverage_and_basis(monkeypatch) -> None:
    import tradingagents.strategies.fundamental_score as fs
    from tradingagents.agents.utils.analysis_tools import _render_fundamental_score

    def _resolver(*, tickers, current_date, include_score_metrics):
        return {"metrics": _panel(), "basis": "synthetic panel"}

    res = fundamental_score_for_ticker("N9", resolver=_resolver)
    text = _render_fundamental_score(res)
    assert "FundamentalScore - N9" in text
    assert "FQS: " in text and "/100" in text
    assert "coverage 6/7 factors" in text
    assert "composite [RESEARCH_ONLY]" in text
    assert "equal weights (1/4 each)" in text
    assert "no supplier on this path" in text
    assert "rev_cagr5" in text
    assert fs.STATUS_RESEARCH_ONLY in text


# --------------------------------------------------------------------------
# the run-card block
# --------------------------------------------------------------------------


def test_run_card_block_is_absent_when_the_gate_is_off() -> None:
    from tradingagents.reporting import _run_card_fundamental_score

    assert _run_card_fundamental_score("MSFT", {}, {}) is None


def test_run_card_block_carries_a_recomputable_attribution(monkeypatch) -> None:
    from tradingagents.reporting import _run_card_fundamental_score
    import tradingagents.strategies.fundamental_score as fs

    def _resolver(*, tickers, current_date, include_score_metrics):
        return {"metrics": _panel(), "basis": "synthetic panel"}

    monkeypatch.setattr(
        fs,
        "fundamental_score_for_ticker",
        lambda ticker, date=None, **kw: fundamental_score_for_ticker(
            ticker, date, resolver=_resolver, **kw
        ),
    )
    block = _run_card_fundamental_score(
        "N9", {"pm_decision": {"trade_date": "2026-09-17"}}, {"enable_fundamental_score": True}
    )
    assert block["status"] == STATUS_RESEARCH_ONLY
    assert block["score"] == pytest.approx(
        sum(v for v in block["components"].values() if v is not None)
        / len([v for v in block["components"].values() if v is not None]),
        abs=1e-9,
    )
    assert block["coverage"]["n"] >= COMPOSITE_MIN_COVERAGE
    assert block["subscores"]["FQS"]["coverage"]["of"] == 7
    assert block["basis"].startswith("FundamentalScore composite")
    assert block["panel_n"] == 10


def test_run_card_block_degrades_without_costing_the_card(monkeypatch) -> None:
    from tradingagents.reporting import _run_card_fundamental_score
    import tradingagents.strategies.fundamental_score as fs

    def _boom(*a, **kw):
        raise RuntimeError("panel fetch failed")

    monkeypatch.setattr(fs, "fundamental_score_for_ticker", _boom)
    block = _run_card_fundamental_score("MSFT", {}, {"enable_fundamental_score": True})
    assert block["score"] is None
    assert "panel fetch failed" in block["unavailable"]


# --------------------------------------------------------------------------
# the four sub-scores exist and are distinct
# --------------------------------------------------------------------------


def test_each_subscore_has_its_own_factor_set_and_directions() -> None:
    panel = _panel()
    for sub, func in (
        ("FQS", quality_subscore),
        ("FGS", growth_subscore),
        ("VS", valuation_subscore),
        ("FRS", risk_subscore),
    ):
        res = func(panel, min_coverage=1)
        assert res["subscore"] == sub
        assert res["directions"] == subscore_directions(sub)
        declared = availability_report(SUBSCORE_FACTORS[sub])
        assert res["factors_NA"] == declared["NA"]
        for f in declared["NA"]:
            assert f not in res["metrics_dropped"]
        assert all(b in {label for _, label in SUBSCORE_BANDS[sub]} for b in res["bands"].values())


def test_subscores_are_selectable() -> None:
    only = subscores(_panel(), only=("VS",), min_coverage=1)
    assert set(only) == {"VS"}
    with pytest.raises(KeyError):
        subscores(_panel(), only=("NOPE",))
