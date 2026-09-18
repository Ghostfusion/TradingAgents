"""The factor schema record (owner decision Q3) - one identity per measure.

Every factor a score engine consumes carries the nine fields Q3 names, so a
sector or security-type overlay is a **data event rather than a code fork**:

``factor / category / formula / direction / base_weight / sector_scope /
normalization_method / supplier / availability``

Three rules this module exists to enforce, all of them the owner's:

- **One identity per measure** (ground rule 2). The `factor` key is the name the
  *panel* carries, and the `formula` names the one function that computes it. A
  second producer of the same measure is a defect, not an alternative.
- **`NA` is not `0`** (master rule 1, Q3). A factor whose `availability` is
  ``NA`` has no supplier on the path that feeds the engine: it is excluded and
  the remaining weights renormalise. It is never manufactured from a generic
  proxy and never scored as zero - a bank without a NIM feed is scored on the
  factors it *does* have.
- **No fabricated coefficients** (ground rule 4). ``base_weight`` is ``None``
  for every factor here: this repo publishes no per-factor weight vector, so the
  engines run equal-weight and *print* that fact rather than inventing one.

`availability` is the *declared* state of the factor on this repo's panel path.
The run-time state is the panel's own: a declared-present factor that a given
name does not carry is simply absent from that name's row, which is what the
coverage floor and `withheld` are for.
"""

from __future__ import annotations

from typing import NamedTuple

# The ten weight-vector categories (`docs/scores/FundamentalScore.md` §2). A
# sector overlay is a scope on these, never a new set.
CATEGORIES: tuple[str, ...] = (
    "Profitability / Quality",
    "Growth",
    "Cash Flow",
    "Valuation",
    "Balance Sheet",
    "Earnings / Accounting Quality",
    "Capital Efficiency",
    "Capital Returns",
    "Distress / Financial Risk",
    "Insider Activity",
)

# The four `FundamentalScore` sub-scores (`docs/scores/FundamentalScore.md` §3.1).
SUBSCORES: tuple[str, ...] = ("FQS", "FGS", "VS", "FRS")

# ``availability`` vocabulary.
PRESENT = "present"
NA = "NA"


class FactorSpec(NamedTuple):
    """One factor's schema record. Nine fields, no more (Q3)."""

    factor: str
    category: str
    formula: str
    direction: int
    base_weight: float | None
    sector_scope: str
    normalization_method: str
    supplier: str
    availability: str


def _spec(factor, category, formula, direction, supplier, availability=PRESENT,
          sector_scope="ALL", normalization_method="winsorised-z"):
    """A record with the three repo-wide defaults filled in.

    Every factor here is sector-universal (``ALL``) and normalised the same way,
    because every one of them is scored by ``factors.category_scores``: winsorise
    0.01/0.99 -> cross-sectional z -> direction sign. A factor that needs a
    different scope or a different normalisation gets its own record, and the
    band table that reads it must claim the same thing (§3.2).
    """
    return FactorSpec(
        factor=factor,
        category=category,
        formula=formula,
        direction=int(direction),
        base_weight=None,
        sector_scope=sector_scope,
        normalization_method=normalization_method,
        supplier=supplier,
        availability=availability,
    )


# --- The record ------------------------------------------------------------
#
# Keys are the metric names the peer panel carries (``peer_universe._panel_from_fin``
# and its score-metric extension), so the schema and the data agree by
# construction. `formula` names the ONE producer; where the panel renames a
# producer's own key, the mapping is recorded in the formula string.

FACTOR_SCHEMA: dict[str, FactorSpec] = {
    s.factor: s
    for s in (
        # --- Profitability / Quality ---------------------------------------
        _spec(
            "return_on_equity",
            "Profitability / Quality",
            "ratios.compute_ratios['return_on_equity'] = net_income / total_equity",
            1,
            "strategies/ratios.py",
        ),
        _spec(
            "return_on_assets",
            "Profitability / Quality",
            "ratios.compute_ratios['return_on_assets'] = net_income / total_assets",
            1,
            "strategies/ratios.py",
        ),
        _spec(
            "gp_a",
            "Profitability / Quality",
            "quantitative_scores.gross_profitability -> panel key 'gp_a' (Novy-Marx)",
            1,
            "dataflows/quantitative_scores.py",
        ),
        # --- Earnings / Accounting Quality ---------------------------------
        _spec(
            "f",
            "Earnings / Accounting Quality",
            "quantitative_scores.piotroski_f_score -> panel key 'f'",
            1,
            "dataflows/quantitative_scores.py",
        ),
        _spec(
            "m",
            "Earnings / Accounting Quality",
            "quantitative_scores.beneish_m_score -> panel key 'm'",
            -1,
            "dataflows/quantitative_scores.py",
        ),
        _spec(
            "noa",
            "Earnings / Accounting Quality",
            "quantitative_scores.net_operating_assets -> panel key 'noa'",
            -1,
            "dataflows/quantitative_scores.py",
        ),
        _spec(
            "accruals",
            "Earnings / Accounting Quality",
            "normalized.accruals_ratio(net_income, operating_cashflow, total_assets)",
            -1,
            "strategies/normalized.py",
        ),
        # --- Growth --------------------------------------------------------
        _spec(
            "revenue_yoy",
            "Growth",
            "statement_parsing.sane_revenue_yoy(fin)",
            1,
            "dataflows/statement_parsing.py",
        ),
        _spec(
            "eps_yoy",
            "Growth",
            "statement_parsing.sane_eps_yoy(fin)",
            1,
            "dataflows/statement_parsing.py",
        ),
        _spec(
            "rev_cagr5",
            "Growth",
            "capex_quality_read['rev_cagr5'] (5-year revenue CAGR)",
            1,
            "strategies/capex_quality.py",
            availability=NA,
        ),
        # --- Valuation -----------------------------------------------------
        _spec(
            "ev_ebitda",
            "Valuation",
            "ratios.compute_ratios['ev_ebitda'] = enterprise_value / EBITDA",
            -1,
            "strategies/ratios.py",
        ),
        _spec(
            "ev_ebit",
            "Valuation",
            "ratios.compute_ratios['ev_ebit'] = enterprise_value / operating_income",
            -1,
            "strategies/ratios.py",
        ),
        _spec(
            "ev_sales",
            "Valuation",
            "ratios.compute_ratios['ev_sales'] = enterprise_value / revenue",
            -1,
            "strategies/ratios.py",
        ),
        _spec(
            "price_to_earnings",
            "Valuation",
            "ratios.compute_ratios['price_to_earnings'] = market_cap / net_income",
            -1,
            "strategies/ratios.py",
        ),
        _spec(
            "price_to_book",
            "Valuation",
            "ratios.compute_ratios['price_to_book'] = market_cap / total_equity",
            -1,
            "strategies/ratios.py",
        ),
        _spec(
            "price_to_sales",
            "Valuation",
            "ratios.compute_ratios['price_to_sales'] = market_cap / revenue",
            -1,
            "strategies/ratios.py",
        ),
        _spec(
            "price_to_cash_flow",
            "Valuation",
            "ratios.compute_ratios['price_to_cash_flow'] = market_cap / operating_cashflow",
            -1,
            "strategies/ratios.py",
        ),
        _spec(
            "price_to_free_cash_flow",
            "Valuation",
            "ratios.compute_ratios['price_to_free_cash_flow'] = market_cap / free_cash_flow",
            -1,
            "strategies/ratios.py",
        ),
        _spec(
            "earnings_yield",
            "Valuation",
            "quantitative_scores.earnings_yield(fin) -> panel key 'earnings_yield'",
            1,
            "dataflows/quantitative_scores.py",
        ),
        _spec(
            "fcf_yield",
            "Valuation",
            "capex_quality_read['fcf_yield'] = free_cash_flow / market_cap",
            1,
            "strategies/capex_quality.py",
            availability=NA,
        ),
        _spec(
            "val_z",
            "Valuation",
            "value_dip historical percentile of the name's own multiple (val_z)",
            -1,
            "strategies/value_dip.py",
            availability=NA,
        ),
        _spec(
            "dcf_upside",
            "Valuation",
            "caller-supplied price / fair value, scaled by fundamental_score.dcf_confidence",
            1,
            "caller (confidence grade D - docs/scores/FundamentalScore.md §3.3)",
        ),
        # --- Balance Sheet (liquidity / leverage) ---------------------------
        _spec(
            "debt_to_equity",
            "Balance Sheet",
            "ratios.compute_ratios['debt_to_equity'] = total_debt / total_equity",
            -1,
            "strategies/ratios.py",
        ),
        _spec(
            "current",
            "Balance Sheet",
            "ratios.compute_ratios['current'] = current_assets / current_liabilities",
            1,
            "strategies/ratios.py",
        ),
        _spec(
            "quick",
            "Balance Sheet",
            "ratios.compute_ratios['quick'] = (current_assets - inventory) / current_liabilities",
            1,
            "strategies/ratios.py",
        ),
        # --- Distress / Financial Risk --------------------------------------
        _spec(
            "z",
            "Distress / Financial Risk",
            "quantitative_scores.altman_z_score -> panel key 'z'",
            1,
            "dataflows/quantitative_scores.py",
        ),
        _spec(
            "o",
            "Distress / Financial Risk",
            "normalized.ohlson_o_score(...)['score'] -> panel key 'o'",
            -1,
            "strategies/normalized.py",
        ),
        _spec(
            "zmijewski_x",
            "Distress / Financial Risk",
            "normalized.zmijewski_score(net_income, total_assets, total_liabilities)",
            -1,
            "strategies/normalized.py",
        ),
    )
}

# Which factors each `FundamentalScore` sub-score consumes.
#
# ``o`` (Ohlson) belongs to FRS alone. `docs/scores/FundamentalScore.md` §3.1
# listed it in FQS *and* FRS, which would put one number into two categories of
# the same composite - the double count master rule 15 forbids. It is a distress
# probability, so FRS owns it and FQS does not read it.
SUBSCORE_FACTORS: dict[str, tuple[str, ...]] = {
    "FQS": (
        "return_on_equity",
        "return_on_assets",
        "gp_a",
        "f",
        "m",
        "noa",
        "accruals",
    ),
    "FGS": ("revenue_yoy", "eps_yoy", "rev_cagr5"),
    "VS": (
        "ev_ebitda",
        "ev_ebit",
        "ev_sales",
        "price_to_earnings",
        "price_to_book",
        "price_to_sales",
        "price_to_cash_flow",
        "price_to_free_cash_flow",
        "earnings_yield",
        "fcf_yield",
        "val_z",
        "dcf_upside",
    ),
    "FRS": ("z", "o", "zmijewski_x", "debt_to_equity", "current", "quick"),
}


def specs_for(factors) -> list[FactorSpec]:
    """The schema records for these factors, in the given order."""
    return [FACTOR_SCHEMA[f] for f in factors]


def directions_for(factors) -> dict[str, int]:
    """``{factor: +1 | -1}`` - the direction table ``category_scores`` consumes."""
    return {f: FACTOR_SCHEMA[f].direction for f in factors}


def weights_for(factors) -> dict[str, float] | None:
    """``{factor: weight}`` when a vector is published, else ``None`` (equal).

    ``None`` is the honest answer here and the engines print it: no per-factor
    weight vector is published in this repo, so the composite runs equal-weight.
    """
    if any(FACTOR_SCHEMA[f].base_weight is not None for f in factors):
        return {f: float(FACTOR_SCHEMA[f].base_weight or 0.0) for f in factors}
    return None


def availability_report(factors) -> dict[str, list[str]]:
    """``{"present": [...], "NA": [...]}`` for a factor set - the printed gap."""
    present = [f for f in factors if FACTOR_SCHEMA[f].availability == PRESENT]
    absent = [f for f in factors if FACTOR_SCHEMA[f].availability == NA]
    return {"present": present, "NA": absent}


def subscore_directions(subscore: str) -> dict[str, int]:
    """The direction table for one sub-score."""
    if subscore not in SUBSCORE_FACTORS:
        raise KeyError(f"unknown sub-score {subscore!r}; known: {sorted(SUBSCORE_FACTORS)}")
    return directions_for(SUBSCORE_FACTORS[subscore])


def validate_schema(table: dict | None = None) -> None:
    """Assert the record's own invariants; raise ``ValueError`` on a violation.

    Called by the tests rather than at import: a schema violation must fail a
    build, not take the package down at import time.
    """
    table = FACTOR_SCHEMA if table is None else table
    seen: set[str] = set()
    for key, s in table.items():
        if key != s.factor:
            raise ValueError(f"schema key {key!r} != record factor {s.factor!r}")
        if s.factor in seen:
            raise ValueError(f"duplicate factor {s.factor!r}")
        seen.add(s.factor)
        if s.direction not in (1, -1):
            raise ValueError(f"{s.factor}: direction must be +1/-1, got {s.direction!r}")
        if s.availability not in (PRESENT, NA):
            raise ValueError(f"{s.factor}: availability must be {PRESENT!r}/{NA!r}")
        if s.category not in CATEGORIES:
            raise ValueError(f"{s.factor}: unknown category {s.category!r}")
        for field in ("formula", "sector_scope", "normalization_method", "supplier"):
            if not str(getattr(s, field)).strip():
                raise ValueError(f"{s.factor}: empty {field}")
    for sub, factors in SUBSCORE_FACTORS.items():
        if sub not in SUBSCORES:
            raise ValueError(f"unknown sub-score {sub!r}")
        for f in factors:
            if f not in table:
                raise ValueError(f"{sub}: {f!r} has no schema record")
    # No factor may enter two sub-scores (master rule 15: one number, one
    # category of the composite).
    counts: dict[str, list[str]] = {}
    for sub, factors in SUBSCORE_FACTORS.items():
        for f in factors:
            counts.setdefault(f, []).append(sub)
    doubled = {f: subs for f, subs in counts.items() if len(subs) > 1}
    if doubled:
        raise ValueError(f"factor(s) in more than one sub-score: {doubled}")
