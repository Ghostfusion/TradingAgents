"""The measurement contract: no leaf prints a statement number unqualified.

This is P4 of the Fact layer, in the shape this repo already uses for a
machine-checked declaration (``tests/test_gate_env_toggles.py`` asserts a doc
against a registry by set equality). Three gates:

1. **The unit registry is complete.** Every canonical statement key the parser
   can produce is declared in ``facts.FACT_UNITS``. Adding an alias to
   ``statement_parsing._ROW_ALIASES`` (or a derived ratio to
   ``enrich_screen_ratios``) without declaring its unit fails here - which is
   how "no leaf prints an undeclared number" becomes checked rather than hoped
   for.
2. **The gate changes qualifiers, never values.** With one fixed
   canonical/provenance pair, ``enable_fact_layer`` ON vs OFF must differ ONLY
   in the qualifier line(s): a Fact layer that moved a number would be a defect
   of the layer, not a feature of it.
3. **A leaf qualifies from the pair it consumed.** The gate must not cause a
   second vendor pull: two consecutive ``fetch_ticker`` calls are not
   deterministic across this chain (GMED 2026-10-14 returned different payload
   sets, P/E 19.05 -> 19.14), so a qualifier built from a second read would
   describe a different measurement than the number it qualifies.
"""

import difflib

import pytest

from tradingagents.agents.utils import analysis_tools as AT
from tradingagents.dataflows import statement_parsing as SP
from tradingagents.dataflows.date_window import set_run_trade_date
from tradingagents.strategies.facts import FACT_UNITS, UNIT_LABELS

pytestmark = pytest.mark.timeout(120)

DAY = "2026-10-14"

#: The canonical MEASUREMENT keys the parser can produce: every ``_ROW_ALIASES``
#: key, plus the canonicals ``fetch_ticker`` derives (``working_capital``) and
#: ``enrich_screen_ratios`` computes. ``currency`` is a marker, not a
#: measurement, and is declared as ``text``.
DERIVED_CANONICAL_KEYS = {
    "working_capital",
    "roa",
    "leverage",
    "current_ratio",
    "gross_margin",
    "asset_turnover",
    "shares_issued",
}
MARKER_KEYS = {"currency"}

FIN = {
    "revenue": {"current": 5_100_000_000.0, "prior": 4_370_000_000.0},
    "operating_income": {"current": 1_030_000_000.0, "prior": 943_000_000.0},
    "net_income": {"current": 933_000_000.0, "prior": 733_000_000.0},
    "total_assets": {"current": 9_000_000_000.0, "prior": 8_800_000_000.0},
    "total_equity": {"current": 7_200_000_000.0, "prior": 6_900_000_000.0},
    "total_liabilities": {"current": 1_800_000_000.0, "prior": 1_900_000_000.0},
    "current_assets": {"current": 3_600_000_000.0, "prior": 3_400_000_000.0},
    "current_liabilities": {"current": 850_000_000.0, "prior": 830_000_000.0},
    "cash": 595_140_000.0,
    "cash_and_investments": 595_140_000.0,
    "total_debt": 111_190_000.0,
    "operating_cashflow": 750_000_000.0,
    "capex": 120_000_000.0,
    "market_cap": 10_245_000_000.0,
    "shares": 134_279_508.0,
    "eps": 7.02,
    "sector": "Healthcare",
    "currency": "USD",
}


def _provenance(period: str = "2026-06-30", *, basis: str = "annual", kind: str = "unstated") -> dict:
    """A provenance map for the fixture, one source per statement."""
    rows = {
        "get_balance_sheet": (
            "cash", "cash_and_investments", "total_debt", "total_assets",
            "total_equity", "total_liabilities", "current_assets", "current_liabilities",
        ),
        "get_income_statement": ("revenue", "operating_income", "net_income", "eps"),
        "get_cashflow": ("operating_cashflow", "capex"),
    }
    out = {
        key: {
            "source": source,
            "basis": basis,
            "period": period,
            "observed_kind": kind,
            "basis_conflict": False,
        }
        for source, keys in rows.items()
        for key in keys
    }
    out["market_cap"] = {
        "source": "get_fundamentals",
        "basis": "info",
        "period": None,
        "observed_kind": "unstated",
        "basis_conflict": False,
    }
    out["sector"] = {
        "source": "get_fundamentals",
        "basis": "info",
        "period": None,
        "observed_kind": "unstated",
        "basis_conflict": False,
    }
    out["shares"] = {
        "source": "derived",
        "basis": "market_cap / price",
        "period": None,
        "observed_kind": "unstated",
        "basis_conflict": False,
    }
    return out


def _patch_fetch(
    monkeypatch,
    *,
    period: str = "2026-06-30",
    basis: str = "annual",
    kind: str = "unstated",
    calls: list | None = None,
):
    """Pin the vendor chain to one deterministic pair, counting the pulls."""

    def fake_fetch(ticker, curr_date, *, with_provenance=False, with_sec_series=False):
        if calls is not None:
            calls.append(ticker)
        if with_provenance:
            return dict(FIN), _provenance(period, basis=basis, kind=kind)
        return dict(FIN)

    monkeypatch.setattr(SP, "fetch_ticker", fake_fetch)
    return fake_fetch


def _run(monkeypatch, gate: bool, invoke):
    from tradingagents.dataflows.config import reset_config, set_config

    set_run_trade_date(DAY)
    set_config({"enable_fact_layer": gate})
    try:
        return invoke()
    finally:
        reset_config()


def test_every_canonical_measurement_key_declares_a_unit():
    """The unit registry is held to the parser's own key set."""
    expected = set(SP._ROW_ALIASES) | DERIVED_CANONICAL_KEYS | MARKER_KEYS
    undeclared = sorted(expected - set(FACT_UNITS))
    extra = sorted(set(FACT_UNITS) - expected)
    assert not undeclared, (
        f"canonical keys with no declared unit in facts.FACT_UNITS: {undeclared} "
        "- a unit is a declaration about the measurement, so a new statement field "
        "must declare one (see docs/design_fact_layer.md)"
    )
    assert not extra, f"facts.FACT_UNITS declares keys the parser cannot produce: {extra}"
    assert set(FACT_UNITS.values()) <= set(UNIT_LABELS)


def test_a_clean_reading_is_byte_identical_across_the_gate(monkeypatch):
    """With one fixed pair whose qualifiers the legacy line can already state,
    the Fact layer adds nothing: a difference here would be a defect."""
    _patch_fetch(monkeypatch)
    off = _run(monkeypatch, False, lambda: AT.get_analyst_verdict.invoke(
        {"ticker": "TEST", "current_date": DAY}
    ))
    on = _run(monkeypatch, True, lambda: AT.get_analyst_verdict.invoke(
        {"ticker": "TEST", "current_date": DAY}
    ))
    assert off == on


def test_the_gate_adds_a_qualifier_without_moving_a_value(monkeypatch):
    """A quarter whose 10-Q is not yet due: the qualifier gains the availability
    verdict, and every screen VALUE stays identical."""
    _patch_fetch(monkeypatch, period="2026-09-30", basis="quarterly", kind="quarterly")
    off = _run(monkeypatch, False, lambda: AT.get_analyst_verdict.invoke(
        {"ticker": "TEST", "current_date": DAY}
    ))
    on = _run(monkeypatch, True, lambda: AT.get_analyst_verdict.invoke(
        {"ticker": "TEST", "current_date": DAY}
    ))
    changed = [
        line
        for line in difflib.unified_diff(off.splitlines(), on.splitlines(), lineterm="", n=0)
        if line.startswith(("-", "+")) and not line.startswith(("---", "+++"))
    ]
    assert changed, "the gate produced no difference on an unfiled period"
    assert all(
        "basis:" in line or "NOT FILED YET" in line or "PARTIAL" in line
        for line in changed
    ), f"the gate moved a value, not just a qualifier: {changed}"

    def screens(text: str) -> list[str]:
        return [
            ln for ln in text.splitlines()
            if ":" in ln and not ln.strip().startswith(("basis:", "|"))
        ]

    assert screens(off) == screens(on)


def test_the_qualifier_names_the_period_of_the_values_it_qualifies(monkeypatch):
    _patch_fetch(monkeypatch)
    on = _run(monkeypatch, True, lambda: AT.get_analyst_verdict.invoke(
        {"ticker": "TEST", "current_date": DAY}
    ))
    qualifier = [ln for ln in on.splitlines() if ln.strip().startswith("basis:")]
    assert len(qualifier) == 1
    line = qualifier[0]
    assert "2026-06-30" in line
    assert "(get_balance_sheet)" in line
    assert "(get_income_statement)" in line
    assert "(get_fundamentals)" in line


def test_a_not_yet_filed_period_is_named_in_the_leaf_qualifier(monkeypatch):
    """A quarter ending 2026-09-30 cannot have a FILED 10-Q basis on
    2026-10-14 (due 2026-11-16 at the fail-closed filer bound)."""
    _patch_fetch(monkeypatch, period="2026-09-30", basis="quarterly", kind="quarterly")
    on = _run(monkeypatch, True, lambda: AT.get_analyst_verdict.invoke(
        {"ticker": "TEST", "current_date": DAY}
    ))
    assert "NOT FILED YET" in on
    assert "2026-11-16" in on


def test_the_gate_never_causes_a_second_vendor_pull(monkeypatch):
    """A qualifier must be built from the pair the leaf already consumed."""
    calls: list = []
    _patch_fetch(monkeypatch, calls=calls)
    _run(monkeypatch, True, lambda: AT.get_analyst_verdict.invoke(
        {"ticker": "TEST", "current_date": DAY}
    ))
    assert len(calls) == 1, f"the leaf pulled the vendor chain {len(calls)}x; expected 1"


def test_the_dcf_fair_value_fact_is_partial_when_a_bridge_leg_is_assumed(monkeypatch):
    """A fair value whose cash or debt leg was ASSUMED 0 is not a measurement
    over a fully measured input set, so its coverage must say so."""
    _patch_fetch(monkeypatch)

    def fake_context(ticker, current_date, *, erp=0.05):
        return {
            "error": None,
            "fin": dict(FIN),
            "provenance": _provenance(),
            "fcf": [630_000_000.0],
            "fcf_latest": 630_000_000.0,
            "shares": 134_279_508.0,
            "shares_basis": "derived",
            "rf": 0.0521,
            "beta": 0.97,
            "beta_assumed": False,
            "erp": erp,
            "cash": 0.0,
            "debt": 0.0,
            "cash_assumed": True,
            "debt_assumed": False,
            "cash_basis": "cash + ST investments @ 2026/Q2",
            "debt_basis": "total debt @ 2026/Q2",
            "cash_debt_note": "; cash assumed 0 (not reported)",
            "market_cap": 10_245_000_000.0,
            "price": 10_245_000_000.0 / 134_279_508.0,
        }

    monkeypatch.setattr(AT, "_dcf_context", fake_context)
    on = _run(monkeypatch, True, lambda: AT.get_dcf_valuation.invoke(
        {"ticker": "TEST", "current_date": DAY}
    ))
    assert "fair_value_fact:" in on
    assert "PARTIAL" in on
    assert "cash_and_investments" in on
    # The gate-off path adds no such line at all.
    off = _run(monkeypatch, False, lambda: AT.get_dcf_valuation.invoke(
        {"ticker": "TEST", "current_date": DAY}
    ))
    assert "fair_value_fact" not in off
    assert off in on  # gate-on is the gate-off text plus the qualifier block
