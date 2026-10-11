"""The per-run quality x cost join (Dream-RSI Phase B; ``docs/design_dream_rsi_replay_simulator.md`` §4.3).

The project measures **quality** (``verify_flags.json``: the per-stem verifier
blocks and the prose pass) and **cost** (``run_card.json``'s ``llm_cost_est``: the
rate-table row per model plus a cap-bound output leg) in separate artifacts and
never joins them, so "was this run's depth worth its cost" has no artifact to
read. This module is that join - pure, offline, no new vendor call and **no writer
change**: both inputs already exist on disk beside each other.

Three honesty constraints, all structural:

* the cost leg is a **cap bound, not a measurement**. ``llm_cost_est`` reports the
  output leg at the configured ``max_output`` cap because per-run token counts are
  not tracked, so every cost field here is named ``*_upper_usd`` and the
  ``caveat`` says so; a model with no rate-table entry contributes ``None`` and is
  listed by name, never 0.0;
* the quality leg is **read, never re-derived** from the verifier's own blocks. A
  tree with no ``verify_flags.json`` (the pass is opt-in) is ``available=False``
  with the reason - never a perfect score by absence;
* the efficiency ratio is reported only when **both** legs are measured, because a
  missing cost has no cost efficiency.

``depth`` is deliberately ``None``: ``run_card.json`` records the models and the
debate outcome, **not** the research-depth knob, so the join answers cost-vs-quality
per run today and cannot yet attribute the cost to a depth. That gap is the
Phase-B finding, and it is stated in the read rather than papered over with a
proxy.
"""

from __future__ import annotations

import math

__all__ = ["COST_LEG_KEY", "RUN_CARD_COST_KEY", "run_economics"]

#: The ``run_card.json`` key holding the per-model rate rows (``reporting.py``'s
#: ``_run_card_llm_cost_est``). Named here so a rename is a one-line change.
RUN_CARD_COST_KEY = "llm_cost_est"

#: The per-leg field carrying the cap-bound output cost.
COST_LEG_KEY = "max_output_leg_usd"

#: Verifier ``overall`` values that are NOT a flag. Anything else - FLAG, or a
#: status the verifier adds later - counts as one, so a new status under-reports
#: nothing.
_CLEAN_OVERALL = ("PASS", "OK")


def _is_flag(overall) -> bool:
    """True when a verifier block's ``overall`` is anything but clean.

    A missing ``overall`` is not a flag (the block carries no verdict to count).
    """
    if overall is None:
        return False
    return str(overall).strip().upper() not in _CLEAN_OVERALL


def _quality(verify_flags: dict | None) -> dict | None:
    """The quality leg from a parsed ``verify_flags.json`` payload, or None.

    ``stems`` counts the per-stem verdicts (the four analyst reports the verdict
    chain reads), ``prose`` the report-level pass, ``flags_count`` their sum. A
    payload without either block has no quality leg at all.
    """
    if not isinstance(verify_flags, dict):
        return None
    verification = verify_flags.get("verification")
    prose = verify_flags.get("prose")
    if not isinstance(verification, dict) and not isinstance(prose, dict):
        return None
    stems: dict[str, object] = {}
    if isinstance(verification, dict):
        for stem, block in verification.items():
            stems[str(stem)] = (block or {}).get("overall") if isinstance(block, dict) else block
    flagged_stems = sorted(s for s, overall in stems.items() if _is_flag(overall))
    flagged_prose: list[str] = []
    prose_overall = None
    if isinstance(prose, dict):
        prose_overall = prose.get("overall")
        reports = prose.get("reports")
        if isinstance(reports, dict):
            flagged_prose = sorted(
                str(path) for path, block in reports.items()
                if _is_flag((block or {}).get("overall") if isinstance(block, dict) else block)
            )
    return {
        "stems": stems,
        "flagged_stems": flagged_stems,
        "prose_overall": prose_overall,
        "flagged_prose": flagged_prose,
        "flags_count": len(flagged_stems) + len(flagged_prose),
    }


def run_economics(run_card: dict | None, *, verify_flags: dict | None = None) -> dict:
    """Join one run's cap-bound LLM cost to the same run's verifier quality.

    ``run_card`` is the parsed tree's ``run_card.json``; ``verify_flags`` the
    parsed ``verify_flags.json`` beside it (``None`` when the pass did not run).

    Returns ``{"available", "ticker", "generated", "models", "cost_upper_usd",
    "cost_legs", "cost_unpriced_legs", "quality", "flags_per_usd", "depth",
    "unavailable", "basis", "caveat"}``. ``cost_upper_usd`` is the sum of the legs
    that carry a rate row (``None`` when none does); ``flags_per_usd`` is the
    flagged-block count per dollar of that bound (``None`` unless both legs
    measure, and ``None`` - not ``inf`` - on a zero bound).
    """
    unavailable = None
    if not isinstance(run_card, dict):
        unavailable = "no run_card payload"
        run_card = {}
    legs_in = run_card.get(RUN_CARD_COST_KEY)
    models: dict[str, object] = {}
    cost_legs: dict[str, dict] = {}
    unpriced: list[str] = []
    total: float | None = None
    if isinstance(legs_in, dict):
        for leg, block in legs_in.items():
            if not isinstance(block, dict):
                continue
            models[str(leg)] = block.get("model")
            leg_cost = block.get(COST_LEG_KEY)
            if isinstance(leg_cost, (int, float)) and math.isfinite(float(leg_cost)):
                value = float(leg_cost)
                total = value if total is None else total + value
            else:
                value = None
                unpriced.append(str(leg))
            cost_legs[str(leg)] = {
                "model": block.get("model"),
                "rate_usd_per_1m": block.get("rate_usd_per_1m"),
                "cost_upper_usd": value,
            }
    quality = _quality(verify_flags)
    if unavailable is None and not isinstance(legs_in, dict) and quality is None:
        unavailable = "run_card carries no llm_cost_est and no verify_flags payload was supplied"
    flags_per_usd = None
    if total is not None and total > 0.0 and quality is not None:
        flags_per_usd = round(float(quality["flags_count"]) / total, 6)
    if total == 0.0:
        basis = (
            "cost leg present with a zero cap bound and a measured quality leg: no "
            "cost efficiency is defined against a zero denominator"
        )
    else:
        basis = (
            "per-run join of run_card.json's llm_cost_est (cap-bound output leg per "
            "model) against verify_flags.json's own blocks; no new measurement, no "
            "vendor call, no writer change (Dream-RSI Phase B)"
        )
    return {
        "available": unavailable is None,
        "ticker": run_card.get("ticker"),
        "generated": run_card.get("generated"),
        "models": models,
        "cost_upper_usd": None if total is None else round(total, 8),
        "cost_legs": cost_legs,
        "cost_unpriced_legs": sorted(unpriced),
        "quality": quality,
        "flags_per_usd": flags_per_usd,
        "depth": None,
        "depth_unavailable": (
            "run_card.json records the models and the debate outcome, not the "
            "research-depth knob: the join answers cost-vs-quality per run and "
            "cannot yet attribute the cost to a depth"
        ),
        "unavailable": unavailable,
        "basis": basis,
        "caveat": (
            "the cost leg is an UPPER BOUND (the model's rate row at the configured "
            "max_output cap), not a billed measurement; treat flags_per_usd as an "
            "order-of-magnitude read"
        ),
    }
