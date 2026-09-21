"""`RiskScore` (WP-5): the inverted composite, the pinned conventions, the tails.

Covers the plan's own acceptance list (`docs/scores/IMPLEMENTATION_PLAN.md` §5.4)
and the engine document's verification list (`docs/scores/RiskScore.md` §6):

(a) a known negative CVaR and a known positive `stress_loss` align to the same
    favourable direction; (b) a missing correlation input raises the
    coverage-weighted uncertainty and never lowers the score; (c) no-data returns
    `None`; (d) the value appears in no `GATE_PRECEDENCE` check and no
    `risk_multiplier` input; (e) the score reads
    `book_context.measured_book_drawdown` and not
    `regime_state.regime_drawdown`; (f) the printed contributions recompute the
    printed score; (g) the semivariance leg consumes `sqrt(RS-)` with the raw
    sums printed beside it, and a fixture where `RS- + RS+ != RV` **fails** -
    the identity is the test.

Also covers the module's own conventions: the inverted direction, the own band
table (never `SCORE_BANDS`), the absent-is-not-zero rule, the capped count floor,
the equal-weight sub-factor policy, the printed-only components, and the
`book_risk.net_beta` producer.

Offline and deterministic: every input is synthetic, no vendor call.
"""

from __future__ import annotations

import ast
import inspect
import math
import random
from pathlib import Path

import pytest

from tradingagents.strategies.book_risk import net_beta
from tradingagents.strategies.risk_score import (
    BANDS,
    CATEGORY_COMPONENTS,
    CATEGORY_MIN_COVERAGE,
    CATEGORY_ORDER,
    CATEGORY_WEIGHTS,
    COMPONENTS,
    PIN_ABS,
    PIN_CORRELATION,
    PIN_DRAWDOWN,
    PIN_NEGATE,
    PIN_TAIL,
    PRINTED,
    RAMPS,
    RISK_BANDS,
    SCORED,
    STATUS_ADVISORY,
    align_components,
    category_score,
    category_weight_share,
    risk_score,
    semivariance_leg,
)
from tradingagents.strategies.score_engine import align
from tradingagents.strategies.volatility_models import semivariance

# The occurrence keys `EventScore` owns (EventScore.md §0.2: occurrence there,
# exposure here). The two engines read the same producers and must never share a
# component name - the boundary is enforced by naming.
EVENTSCORE_OCCURRENCE_KEYS = {
    "earnings_imminence",
    "earnings_in_window",
    "macro_imminence",
    "macro_count_high",
    "catalyst_unassessed",
    "fed_imminence",
    "fed_modal_prob",
    "opex_imminence",
    "opex_in_week",
    "opex_post_unwind",
    "product_clinical_imminence",
    "court_imminence",
    "investor_day_imminence",
}


def _full_values() -> dict:
    """A moderate book: every scored component measured, all eight categories."""
    return {
        # volatility
        "realized_vol": 0.25,
        "rs_minus": 0.0002,
        "rs_plus": 0.0003,
        "rv": 0.0005,
        "implied_move_pct": 0.03,
        "iv_percentile": 0.40,
        "gex_short_gamma": False,
        # tail
        "cvar": -0.03,
        "portfolio_cvar": -0.035,
        "stress_loss": 0.03,
        "es_pct": 0.04,
        "extreme_quantile_es": -0.05,
        # liquidity
        "amihud_illiquidity": 3e-7,
        "days_to_absorb": 8.0,
        "spread_pct": 0.004,
        "kyle_lambda": 1e-7,
        "liquidity_verdict": "liquid",
        # gap
        "gap_pct": -0.01,
        "gap_atr": 0.8,
        "through_stop": False,
        "premarket_rvol": 1.8,
        # correlation
        "cluster_exposure_share": 0.22,
        "book_correlated_stress": 0.03,
        # concentration
        "portfolio_hhi": 0.15,
        "top_position_share": 0.12,
        "sector_max_share": 0.25,
        # drawdown
        "measured_book_drawdown": 0.06,
        "cdar": 0.08,
        "kill_switch_rung": 1,
        # event
        "catalyst_scale": 0.8,
        "catalyst_risk_penalty": 0.7,
        "event_hard_block": False,
        "opex_window": False,
        "position_mult_by_side": 0.5,
    }


def _at_edge(favourable: bool) -> dict:
    """A book at every scored component's own favourable / unfavourable edge."""
    out: dict = {}
    for name, comp in COMPONENTS.items():
        if comp.kind != SCORED or name == "sqrt_rs_minus":
            continue
        if name in BANDS:
            table = BANDS[name]
            pick = max if favourable else min
            out[name] = pick(table, key=lambda t: t[1])[0]
            continue
        lo, hi = RAMPS[name]
        if comp.direction == "lower_better":
            pinned = lo if favourable else hi
        else:
            pinned = hi if favourable else lo
        if comp.pin == PIN_NEGATE:
            pinned = -pinned
        out[name] = pinned
    sq = RAMPS["sqrt_rs_minus"][0] if favourable else RAMPS["sqrt_rs_minus"][1]
    rm = sq * sq
    out["rs_minus"] = rm
    out["rs_plus"] = 1e-6
    out["rv"] = rm + 1e-6
    return out


# --------------------------------------------------------------------------
# (a) a negative CVaR and a positive stress_loss align the same way
# --------------------------------------------------------------------------


def test_a_negative_cvar_and_a_positive_stress_loss_align_the_same_way() -> None:
    """§0.3: the pinned convention is the POSITIVE loss; the score aligns it."""
    vals = {"cvar": -0.05, "stress_loss": 0.05}
    rows = align_components(vals)
    # the producers disagree in sign; the pinned value does not
    assert rows["cvar"]["raw"] == pytest.approx(-0.05)
    assert rows["stress_loss"]["raw"] == pytest.approx(0.05)
    assert rows["cvar"]["pinned"] == pytest.approx(0.05)
    assert rows["stress_loss"]["pinned"] == pytest.approx(0.05)
    assert rows["cvar"]["aligned"] == rows["stress_loss"]["aligned"]
    # and a bigger loss moves BOTH toward the unfavourable end
    worse = align_components({"cvar": -0.08, "stress_loss": 0.08})
    assert worse["cvar"]["aligned"] < rows["cvar"]["aligned"]
    assert worse["stress_loss"]["aligned"] < rows["stress_loss"]["aligned"]
    better = align_components({"cvar": -0.01, "stress_loss": 0.01})
    assert better["cvar"]["aligned"] > rows["cvar"]["aligned"]
    assert better["stress_loss"]["aligned"] > rows["stress_loss"]["aligned"]


def test_the_engine_is_inverted_relative_to_the_producers_native_loss_sign() -> None:
    """100 = low risk: the favourable edge of every component scores higher."""
    low = risk_score(_at_edge(True))
    high = risk_score(_at_edge(False))
    assert low["score"] is not None and high["score"] is not None
    assert low["score"] > high["score"]
    for cat in CATEGORY_ORDER:
        assert low["categories"][cat]["score"] > high["categories"][cat]["score"], cat


# --------------------------------------------------------------------------
# (b) a missing correlation input raises uncertainty, never lowers the score
# --------------------------------------------------------------------------


def test_a_missing_correlation_input_raises_uncertainty_and_never_lowers_the_score() -> None:
    full = risk_score(_full_values())
    without = {
        k: v for k, v in _full_values().items()
        if k not in COMPONENTS or COMPONENTS[k].category != "correlation"
    }
    res = risk_score(without)
    assert res["score"] is not None
    # the coverage-weighted uncertainty goes UP and the coverage goes DOWN
    assert res["uncertainty"] > full["uncertainty"]
    assert res["coverage"] < full["coverage"]
    # the absent category contributes nothing - never a 0 carrying its weight
    assert res["contributions"]["correlation"]["score"] is None
    assert res["contributions"]["correlation"]["contribution"] is None
    # the printed score is the renormalised mean of what WAS measured ...
    num = sum(
        c["contribution"] for c in res["contributions"].values()
        if c["contribution"] is not None
    )
    den = sum(
        c["weight"] for c in res["contributions"].values() if c["score"] is not None
    )
    assert res["score"] == pytest.approx(num / den, abs=0.005)
    # ... which is strictly ABOVE the punitive NA-as-0 imputation
    total_w = sum(c["weight"] for c in res["contributions"].values())
    zero_imputed = sum(
        (c["contribution"] or 0.0) for c in res["contributions"].values()
    ) / total_w
    assert res["score"] > zero_imputed


# --------------------------------------------------------------------------
# (c) no data
# --------------------------------------------------------------------------


def test_no_data_returns_none_never_zero_and_never_fifty() -> None:
    res = risk_score({})
    assert res["score"] is None
    assert res["coverage"] == 0.0
    assert res["uncertainty"] == 1.0
    assert "floor" in res["withheld"]
    assert res["bands"] is None
    assert res["status"] == STATUS_ADVISORY
    for cat in CATEGORY_ORDER:
        assert res["categories"][cat]["score"] is None


# --------------------------------------------------------------------------
# (d) no gate, no size
# --------------------------------------------------------------------------


def _referenced_names(path: str) -> set[str]:
    tree = ast.parse(Path(path).read_text(encoding="utf-8"))
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
    return referenced


def test_the_value_appears_in_no_gate_precedence_check_and_no_risk_multiplier_input() -> None:
    referenced = _referenced_names("tradingagents/strategies/risk_score.py")
    for forbidden in (
        "GATE_PRECEDENCE",
        "risk_multiplier",
        "RiskMultiplier",
        "risk_governor",
        "decision_guardrail",
        "sizing",
        "position_size",
        "knife_guard",
    ):
        assert not any(forbidden in ref for ref in referenced), (forbidden, referenced)
    # the two-tier multiplier's own input carries no score field or parameter
    from tradingagents.strategies.risk_multiplier import RiskMultiplier, combine

    assert not any("score" in f for f in RiskMultiplier.__dataclass_fields__)
    assert not any("score" in p for p in inspect.signature(combine).parameters)
    # and the executor's 17 precedence checks name no risk score
    contracts = Path("../TradingExecution/signald/contracts.py")
    if contracts.exists():
        src = contracts.read_text(encoding="utf-8")
        assert "GATE_PRECEDENCE" in src
        assert "risk_score" not in src


# --------------------------------------------------------------------------
# (e) one drawdown resolver, and it is the positive one
# --------------------------------------------------------------------------


def test_the_score_reads_book_context_measured_book_drawdown_not_regime_drawdown() -> None:
    dd = COMPONENTS["measured_book_drawdown"]
    assert dd.producer == "book_context.measured_book_drawdown:102"
    assert dd.convention == PIN_DRAWDOWN
    assert "regime_drawdown" not in COMPONENTS
    assert not any("regime_state" in c.producer for c in COMPONENTS.values())
    # the component reads the positive-magnitude KEY; the opposite-sign regime
    # number is not a component and cannot become one by being supplied
    row = align_components({"regime_drawdown": -0.12})["measured_book_drawdown"]
    assert row["raw"] is None and row["aligned"] is None
    res = risk_score({"regime_drawdown": -0.12})
    assert res["categories"]["drawdown"]["score"] is None
    # a positive measured drawdown is the one that scores
    assert align_components({"measured_book_drawdown": 0.06})["measured_book_drawdown"]["pinned"] == pytest.approx(0.06)
    # no import of the regime module either
    modules = {
        n.module or ""
        for n in ast.walk(ast.parse(Path("tradingagents/strategies/risk_score.py").read_text(encoding="utf-8")))
        if isinstance(n, ast.ImportFrom)
    }
    assert not any("regime_state" in m for m in modules)


# --------------------------------------------------------------------------
# (f) the attribution recomputes the score
# --------------------------------------------------------------------------


def test_the_printed_contributions_recompute_the_printed_score() -> None:
    res = risk_score(_full_values())
    num = sum(c["contribution"] for c in res["contributions"].values())
    den = sum(c["weight"] for c in res["contributions"].values())
    assert res["score"] == pytest.approx(num / den, abs=0.005)
    assert res["coverage"] == pytest.approx(den / sum(CATEGORY_WEIGHTS.values()))
    for cat, entry in res["contributions"].items():
        assert entry["score"] == res["categories"][cat]["score"]
        assert entry["contribution"] == pytest.approx(entry["weight"] * entry["score"])


def test_a_supplied_weight_vector_is_printed_and_used() -> None:
    w = dict.fromkeys(CATEGORY_ORDER, 1.0)
    w["tail"] = 4.0
    res = risk_score(_full_values(), weights=w)
    num = sum(w[cat] * res["categories"][cat]["score"] for cat in CATEGORY_ORDER)
    assert res["score"] == pytest.approx(num / sum(w.values()), abs=0.005)
    assert res["weights"] == w
    assert "supplied category weights" in res["basis"]
    assert "owner category weights" in risk_score(_full_values())["basis"]


def test_category_weight_share_renormalises() -> None:
    share = category_weight_share()
    assert sum(share.values()) == pytest.approx(1.0)
    assert share["tail"] == pytest.approx(0.15)
    assert share["volatility"] == pytest.approx(0.15)


# --------------------------------------------------------------------------
# (g) the semivariance leg and its identity
# --------------------------------------------------------------------------


def test_the_semivariance_leg_consumes_sqrt_rs_minus_with_the_raw_sums_printed_beside_it() -> None:
    rm, rp = 0.0002, 0.0003
    vals = {"rs_minus": rm, "rs_plus": rp, "rv": rm + rp}
    row = align_components(vals)["sqrt_rs_minus"]
    expected = math.sqrt(rm)
    assert row["raw"] == pytest.approx(expected)
    assert row["aligned"] == pytest.approx(
        align(expected, direction="lower_better", lo=0.008, hi=0.030)
    )
    # the raw squared-return sums are printed beside it
    assert row["rs_minus"] == pytest.approx(rm)
    assert row["rs_plus"] == pytest.approx(rp)
    assert row["rv"] == pytest.approx(rm + rp)
    assert "RS- + RS+ = RV exactly" in row["identity"]
    assert row["units"].startswith("return units")
    # the ASYMMETRY ratio is a different quantity and is NOT what is consumed
    ratio = rm / rp
    assert row["aligned"] != pytest.approx(
        align(ratio, direction="lower_better", lo=0.008, hi=0.030)
    )
    # a supplied sqrt_rs_minus is honoured, and a wrong one is refused
    supplied = align_components({**vals, "sqrt_rs_minus": expected})["sqrt_rs_minus"]
    assert supplied["raw"] == pytest.approx(expected)
    with pytest.raises(ValueError, match="does not equal"):
        align_components({**vals, "sqrt_rs_minus": expected * 1.5})


def test_a_fixture_where_rs_minus_plus_rs_plus_differs_from_rv_fails() -> None:
    """The identity is the test: a broken decomposition is not a number."""
    broken = {"rs_minus": 0.0002, "rs_plus": 0.0003, "rv": 0.0009}
    with pytest.raises(ValueError, match="identity violated"):
        align_components(broken)
    with pytest.raises(ValueError, match="identity violated"):
        risk_score(broken)
    # an incomplete triple cannot be checked either - refused, never assumed
    with pytest.raises(ValueError, match="missing"):
        align_components({"rs_minus": 0.0002})
    with pytest.raises(ValueError, match="cannot be negative"):
        semivariance_leg({"rs_minus": -0.0002, "rs_plus": 0.0003, "rv": 0.0001})
    # and all-absent is not an error: the leg is simply None
    assert semivariance_leg({})["sqrt_rs_minus"] is None


def test_the_real_semivariance_producer_satisfies_the_identity_the_score_checks() -> None:
    rng = random.Random(11)
    closes = [100.0]
    for _ in range(120):
        closes.append(closes[-1] * (1.0 + rng.gauss(0.0005, 0.012)))
    out = semivariance(closes)
    assert out["rs_minus"] + out["rs_plus"] == pytest.approx(out["rv"], abs=1e-15)
    row = align_components(out)["sqrt_rs_minus"]
    assert row["raw"] == pytest.approx(out["sqrt_rs_minus"])
    assert row["identity"].startswith("RS- + RS+ = RV exactly")
    assert row["aligned"] is not None


# --------------------------------------------------------------------------
# the module's own conventions
# --------------------------------------------------------------------------


def test_every_component_row_prints_its_raw_value_with_units_and_sign() -> None:
    res = risk_score(_full_values())
    for name, row in res["components"].items():
        assert row["units"], name
        assert row["producer"], name
        assert row["direction"] in ("higher_better", "lower_better")
        assert row["category"] in CATEGORY_ORDER
        assert row["kind"] in (SCORED, PRINTED)
        if row["aligned"] is not None:
            assert row["raw"] is not None
            assert row["pinned"] is not None
        if row["pin"] == PIN_NEGATE:
            assert row["pinned"] == pytest.approx(-row["raw"])
        if row["pin"] == PIN_ABS:
            assert row["pinned"] == pytest.approx(abs(row["raw"]))
    # the three pinned conventions are visible on the rows that carry them
    assert res["components"]["cvar"]["convention"] == PIN_TAIL
    assert res["components"]["stress_loss"]["convention"] == PIN_TAIL
    assert res["components"]["cvar"]["raw"] == pytest.approx(-0.03)
    assert res["components"]["cvar"]["pinned"] == pytest.approx(0.03)
    assert res["components"]["measured_book_drawdown"]["convention"] == PIN_DRAWDOWN
    assert res["components"]["measured_book_drawdown"]["pinned"] == pytest.approx(0.06)
    corr = res["components"]["cluster_exposure_share"]
    assert corr["convention"] == PIN_CORRELATION and "proxy" in corr["convention"]
    assert corr["pinned"] == pytest.approx(0.22)
    # the gap sign is not the risk: the magnitude is
    assert res["components"]["gap_pct"]["raw"] == pytest.approx(-0.01)
    assert res["components"]["gap_pct"]["pinned"] == pytest.approx(0.01)


def test_missing_components_are_none_never_a_neutral_fifty() -> None:
    rows = align_components({"cvar": -0.03})
    assert rows["cvar"]["aligned"] is not None
    assert rows["stress_loss"]["aligned"] is None
    assert rows["stress_loss"]["raw"] is None
    assert {n for n, r in rows.items() if r["aligned"] is not None} == {"cvar"}
    assert align_components({"cvar": None})["cvar"]["aligned"] is None
    assert align_components({"cvar": float("nan")})["cvar"]["aligned"] is None
    # an undeclared key is ignored, not scored
    assert "not_a_component" not in align_components({"not_a_component": 1.0})


def test_a_category_floor_is_capped_at_its_own_scored_count() -> None:
    """A category smaller than the floor still scores (the WP-2 FGS lesson)."""
    rows = align_components(_full_values())
    assert len([n for n in CATEGORY_COMPONENTS["correlation"] if COMPONENTS[n].kind == SCORED]) == 2
    res = category_score("correlation", rows, min_coverage=5)
    assert res["score"] is not None
    assert "floor 2" in res["basis"]
    # below the (capped) floor it is withheld WITH the reason, never zero
    partial = {k: v for k, v in _full_values().items() if k != "book_correlated_stress"}
    res2 = category_score("correlation", align_components(partial), min_coverage=CATEGORY_MIN_COVERAGE)
    assert res2["score"] is None
    assert "floor is 2" in res2["withheld"]


def test_no_sub_factor_weight_vector_is_fabricated_and_the_fact_is_printed() -> None:
    res = risk_score(_full_values())
    assert res["weights"] is None  # no override: the owner's table was used
    assert "no sub-factor weight vector is published" in res["basis"]
    for cat in CATEGORY_ORDER:
        entry = res["categories"][cat]
        assert entry["component_weights"] == "equal (no sub-factor vector is published)"
        assert "equal weights (none supplied)" in entry["basis"]


def test_owner_weights_are_the_published_table_and_sum_to_one_hundred() -> None:
    assert sum(CATEGORY_WEIGHTS.values()) == pytest.approx(100.0)
    assert CATEGORY_WEIGHTS == {
        "volatility": 15.0, "tail": 15.0, "liquidity": 10.0, "gap": 10.0,
        "correlation": 15.0, "concentration": 10.0, "drawdown": 15.0, "event": 10.0,
    }


def test_risk_bands_are_not_the_decision_rating_bands() -> None:
    from tradingagents.strategies.decision_guardrail import SCORE_BANDS

    assert tuple(RISK_BANDS) != tuple(SCORE_BANDS)
    assert not {label for _, label in RISK_BANDS} & {label for _, label in SCORE_BANDS}


def test_every_scored_component_has_an_alignment_table() -> None:
    for name, comp in COMPONENTS.items():
        if comp.kind == PRINTED:
            assert name not in BANDS and name not in RAMPS, name
        else:
            assert (name in BANDS) ^ (name in RAMPS), name


def test_band_tables_are_written_top_down() -> None:
    for name, table in BANDS.items():
        edges = [edge for edge, _ in table]
        assert edges == sorted(edges, reverse=True), name
        assert all(0.0 <= score <= 100.0 for _, score in table), name


def test_printed_components_never_enter_the_denominator() -> None:
    vals = _full_values()
    without = {
        k: v for k, v in vals.items()
        if k not in COMPONENTS or COMPONENTS[k].kind == SCORED
    }
    a = risk_score(vals)
    b = risk_score(without)
    assert a["score"] == b["score"]
    assert a["coverage"] == b["coverage"] == pytest.approx(1.0)
    for name in ("kyle_lambda", "liquidity_verdict", "position_mult_by_side"):
        row = a["components"][name]
        assert row["kind"] == PRINTED
        assert row["aligned"] is None
        assert row["raw"] == vals[name]
        assert name in a["printed"]


def test_status_is_advisory_and_the_basis_names_the_conventions() -> None:
    res = risk_score(_full_values())
    assert res["status"] == STATUS_ADVISORY == "ADVISORY"
    assert "INVERTED (100 = low risk)" in res["basis"]
    for pinned in (PIN_TAIL, PIN_DRAWDOWN, PIN_CORRELATION):
        assert pinned in res["basis"]
    assert "never a gate, never a size" in res["basis"]


def test_category_score_rejects_an_unknown_category() -> None:
    with pytest.raises(KeyError):
        category_score("nope", {})


def test_the_event_leg_is_disjoint_from_eventscore_occurrence_keys() -> None:
    """Master rule 3 / plan §5.7(d): same producers, disjoint component keys."""
    module = __import__("tradingagents.strategies.risk_score", fromlist=["*"])
    keys: set[str] = set()
    for name in dir(module):
        if not name.isupper():
            continue
        obj = getattr(module, name)
        if isinstance(obj, (dict, tuple, list)):
            keys |= {k for k in obj if isinstance(k, str)}
    assert not keys & EVENTSCORE_OCCURRENCE_KEYS, keys & EVENTSCORE_OCCURRENCE_KEYS
    # and this engine's event leg is the EXPOSURE measures
    event_keys = set(CATEGORY_COMPONENTS["event"])
    assert {"catalyst_scale", "catalyst_risk_penalty"} <= event_keys
    assert not event_keys & EVENTSCORE_OCCURRENCE_KEYS


def test_the_module_never_touches_the_sizing_path() -> None:
    """No import and no attribute access on the sizing path (the docstring's
    mention of `risk/sizing.py` is prose, and prose is not a dependency)."""
    referenced = _referenced_names("tradingagents/strategies/risk_score.py")
    for forbidden in (
        "sizing",
        "risk.sizing",
        "risk_multiplier",
        "knife_guard",
        "position_size",
        "decision_guardrail",
        "risk_governor",
    ):
        assert not any(forbidden in ref for ref in referenced), (forbidden, referenced)


# --------------------------------------------------------------------------
# the book_risk.net_beta producer (RiskScore §3.3 / plan §5.4)
# --------------------------------------------------------------------------


def test_net_beta_is_the_weight_sum_of_betas() -> None:
    weights = {"AAPL": 0.3, "MSFT": 0.2, "CASH_LIKE": 0.0}
    betas = {"AAPL": 1.2, "MSFT": 0.8, "CASH_LIKE": 5.0}
    assert net_beta(weights, betas) == pytest.approx(0.3 * 1.2 + 0.2 * 0.8)
    # a negative beta is a real hedge and keeps its sign
    assert net_beta({"HEDGE": 0.5}, {"HEDGE": -1.0}) == pytest.approx(-0.5)


def test_net_beta_is_none_when_a_weighted_name_has_no_beta() -> None:
    """NA is not 0: a missing per-name beta makes the BOOK's beta unknown."""
    assert net_beta({"AAPL": 0.5, "NVDA": 0.5}, {"AAPL": 1.1}) is None
    assert net_beta({"AAPL": 0.5}, {"AAPL": None}) is None
    assert net_beta({"AAPL": 0.5}, {"AAPL": float("nan")}) is None


def test_net_beta_is_none_for_an_empty_or_all_zero_book() -> None:
    assert net_beta({}, {}) is None
    assert net_beta({"AAPL": 0.0}, {"AAPL": 1.2}) is None


def test_net_beta_treats_an_uninvested_remainder_as_zero_beta_cash() -> None:
    # weights summing below 1.0 leave a cash sleeve: beta 0 by construction, so
    # the book's beta is the invested part's, never renormalised up to 1.0
    assert net_beta({"AAPL": 0.5}, {"AAPL": 2.0}) == pytest.approx(1.0)
