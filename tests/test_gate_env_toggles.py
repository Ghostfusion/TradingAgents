"""Every gate is flippable from `.env`, and the gate registry is machine-true.

Docs: `docs/gate_registry.md`. Three audits found gates that could not fire, so
the registry exists to keep each gate's claim next to the thing that proves it.
This module enforces the parts a machine can check:

1. the doc's key set equals the registry below (the doc cannot drift);
2. every key exists in DEFAULT_CONFIG and has an `_ENV_OVERRIDES` row;
3. flipping each key through the REAL loader (`_apply_env_overrides`, the same
   path `.env` takes) works in BOTH directions;
4. every registry env var appears in `.env.example`;
5. the Status column is true: a `wired` gate is referenced outside
   `default_config.py`, an `inert` gate is referenced by nothing.

What this cannot check is whether a gate's test actually has teeth - that is what
the "Proven by" column and the phase mutation lists are for.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

import tradingagents.default_config as dc

REPO = Path(__file__).resolve().parents[1]
DOC = REPO / "docs" / "gate_registry.md"
ENV_EXAMPLE = REPO / ".env.example"

# Canonical registry. The doc must match this exactly (set equality), and the
# Status column must be true in the source. Adding a gate means adding it here,
# to the doc, to DEFAULT_CONFIG, and to _ENV_OVERRIDES.
REGISTRY: dict[str, str] = {
    # decision gates
    "enable_risk_governor": "wired",
    "enable_liquidity_gate": "wired",
    "enable_hard_guards": "wired",
    "enable_position_contract": "wired",
    "enable_tranche_risk": "wired",
    "enable_calibration": "wired",
    "enable_agreement": "wired",
    "enable_decision_guardrail": "wired",
    "enable_exits": "wired",
    "enable_kelly_alloc": "wired",
    "enable_correlation_penalty": "wired",
    "enable_pre_market_review": "wired",
    "enable_jev_verdict": "wired",
    "enable_preopen_depth": "wired",
    "risk_audit_enabled": "wired",
    "regime_state_enable": "wired",
    "vol_cap_enable": "wired",
    "enable_sector_multifactor": "wired",
    "enable_sector_industry": "wired",
    "enable_sector_breadth": "wired",
    "enable_sector_eodhd_constituents": "wired",
    "enable_mechanical_volume_discount": "wired",
    "enable_spread_estimator": "wired",
    "enable_book_risk_sizing": "wired",
    "enable_conformal_bands": "wired",
    "enable_return_decomposition": "wired",
    "enable_text_factors": "wired",
    "enable_bocpd": "wired",
    # Paper-survey adoption, waves 0-1 and the T1 batch (docs/paper_survey_26/).
    "enable_coverage_window": "wired",
    "enable_rn_skew_proxy": "wired",
    "enable_trend_spectral": "wired",
    "enable_trial_ledger": "wired",
    "enable_jump_robust_proxies": "wired",
    "enable_mp_lower_spectrum": "wired",
    "enable_long_memory": "wired",
    "enable_bootstrap_intervals": "wired",
    "enable_event_iv_lift": "wired",
    "enable_triadic_stress": "wired",
    "enable_refusal_ledger": "wired",
    "enable_materiality_verdict": "wired",
    "enable_accuracy_ceiling": "wired",
    "enable_spectral_null_band": "wired",
    "enable_rnd_recovery": "wired",
    "enable_eigen_rotation": "wired",
    "enable_drawdown_envelope": "wired",
    "enable_hmm_heavy_tails": "wired",
    "enable_tail_risk_layer": "wired",
    "enable_factor_availability_gate": "wired",
    "enable_forward_stress_probability": "wired",
    "enable_prompt_condition_harness": "wired",
    "backtest_limit_threshold": "wired",
    "backtest_volume_participation": "wired",
    # debate-integrity gates
    "debate_require_capability_matrix": "wired",
    "debate_baseline_fallback": "wired",
    # numeric limits the gates read
    "max_position_pct": "wired",
    "risk_max_position_pct": "wired",
    "sector_cap_limit": "wired",
    "risk_max_drawdown_pct": "wired",
    "risk_daily_cvar_budget_pct": "wired",
    "risk_daily_loss_budget_pct": "wired",
    "risk_hwm_soft_pct": "wired",
    "risk_hwm_hard_pct": "wired",
    "catalyst_hard_block_days": "wired",
    "market_stress_vol_cap": "wired",
    "value_dip_regime_vol_cap": "wired",
    # data-surface gates (add a source, never a decision)
    "enable_moomoo_snapshot": "wired",
    "enable_analyst_estimates": "wired",
    "enable_eodhd_rates": "wired",
    # Benzinga event surface: guidance revisions, FDA milestones, secondary
    # offerings, individual analyst actions, news retractions. One gate for the
    # whole surface - one vendor, one risk profile, one opt-in.
    "enable_benzinga_surface": "wired",
    # These two shipped with a DEFAULT_CONFIG entry, an _ENV_OVERRIDES row and a
    # .env.example line but NO row here and no doc row, so the five-place rule
    # was unmet. They were also unregisterable: their only read site is
    # `_feature_gate("enable_x", ...)`, an idiom the Status scan did not match.
    # The scan now matches it, so both can be declared honestly.
    "enable_options_surface": "wired",
    "enable_risk_free_curve": "wired",
    # context gates (change what the decision model reads, never a decision)
    "enable_decision_packet": "wired",
    "enable_context_expansion": "wired",
    "enable_decision_challenge": "wired",
    # The one context gate defaulting True: the Phase A-E block was built
    # unconditionally while its documented env var was inert, so "always on"
    # is the shipped behaviour and the default must not change it.
    "enable_computed_context": "wired",
    # SecurityContext (docs/design_security_context.md). A classification
    # front end: it reads cached identity, makes no network call, and writes
    # one advisory card key. The prior it prints cannot gate - the candidate
    # set is the union of every registered theme with the prior's picks.
    "enable_security_context": "wired",
    # declared but read by nothing (see registry section 4)
    "enable_threshold_gate": "inert",
    "enable_risk_manager": "inert",
    "enable_skill_overlays": "inert",
    "enable_trailing_exit": "inert",
    "value_dip_regime_gate": "inert",
    "volume_share_vol_limit": "inert",
    "enable_regime": "inert",
    "enable_factors": "inert",
}

_ROW_RE = re.compile(r"^\|\s*`([a-z0-9_]+)`\s*\|(.+)\|\s*$")


def _doc_rows() -> dict[str, tuple[str, str]]:
    """{key: (env var, status)} from the registry tables."""
    rows: dict[str, tuple[str, str]] = {}
    for line in DOC.read_text(encoding="utf-8").splitlines():
        m = _ROW_RE.match(line)
        if not m:
            continue
        key = m.group(1)
        cells = [c.strip() for c in m.group(2).split("|")]
        env = next((c.strip("`") for c in cells if c.startswith("`TRADINGAGENTS_")), "")
        status = cells[-1].strip()
        rows[key] = (env, status)
    return rows


def _read_sites(key: str) -> list[str]:
    """Files that READ ``key`` as a config value (excluding config/tests/docs).

    A plain substring search is not enough: `enable_skill_overlays` appears in
    two docstrings and is read by nothing, and calling that "wired" would defeat
    the point of the registry. So the key must appear as a quoted literal in an
    access idiom (``cfg.get("key")``, ``config["key"]``, ``_flag("key")``,
    ``_feature_gate("key", ...)``, a comparison, a membership test). Root-level
    entry points (``batch.py``) count too - a gate read there is still a gate.

    ``_feature_gate`` was added to the idiom list on 2026-09-20: it is the
    established pattern for a gated analyst tool (the flag key is its first
    argument), and while it was absent every gate using it was unregisterable -
    the scan found no read site, so the registry could only have called a live
    gate ``inert``. ``enable_options_surface`` and ``enable_risk_free_curve``
    were in exactly that state.
    """
    pattern = re.compile(
        r"""(?:\.get\(|\[|_flag\(|_feature_gate\(|==|!=|in\s*\(|in\s*\{|\bor\b\s*)\s*["']"""
        + re.escape(key)
        + r"""["']"""
    )
    hits = []
    candidates = [
        path
        for base in ("tradingagents", "scripts")
        for path in (REPO / base).rglob("*.py")
    ]
    candidates += list(REPO.glob("*.py"))
    for path in candidates:
        if path.name == "default_config.py":
            continue
        if pattern.search(path.read_text(encoding="utf-8", errors="ignore")):
            hits.append(path.relative_to(REPO).as_posix())
    return hits


def test_the_registry_doc_matches_the_canonical_registry():
    """Drift gate: a gate added to one side must be added to the other."""
    doc = _doc_rows()
    assert set(doc) == set(REGISTRY), (
        f"doc-only: {sorted(set(doc) - set(REGISTRY))}; "
        f"registry-only: {sorted(set(REGISTRY) - set(doc))}"
    )
    for key, status in REGISTRY.items():
        assert doc[key][1] == status, f"{key}: doc says {doc[key][1]!r}, registry {status!r}"


def test_every_gate_exists_in_the_config_and_has_an_env_row():
    from tradingagents.default_config import _ENV_OVERRIDES

    env_to_key = dict(_ENV_OVERRIDES)
    key_to_env = {v: k for k, v in env_to_key.items()}
    missing_key = [k for k in REGISTRY if k not in dc.DEFAULT_CONFIG]
    missing_env = [k for k in REGISTRY if k not in key_to_env]
    assert not missing_key, f"registry keys absent from DEFAULT_CONFIG: {missing_key}"
    assert not missing_env, (
        "these gates cannot be set from .env (no _ENV_OVERRIDES row): "
        f"{missing_env}"
    )
    # The doc must name the env var the loader actually uses.
    doc = _doc_rows()
    wrong = {k: doc[k][0] for k in REGISTRY if doc[k][0] != key_to_env[k]}
    assert not wrong, f"doc env vars disagree with _ENV_OVERRIDES: {wrong}"


def test_every_gate_flips_through_the_real_env_loader(monkeypatch):
    """Both directions, through `_apply_env_overrides` - the .env path itself."""
    from tradingagents.default_config import _ENV_OVERRIDES

    key_to_env = {v: k for k, v in _ENV_OVERRIDES.items()}
    for key, _status in REGISTRY.items():
        env = key_to_env[key]
        current = dc.DEFAULT_CONFIG[key]
        if isinstance(current, bool):
            target = not current
            monkeypatch.setenv(env, "true" if target else "false")
            out = dc._apply_env_overrides(dict(dc.DEFAULT_CONFIG))
            assert out[key] is target, f"{key}: {env} did not set it to {target}"
        elif isinstance(current, int) and not isinstance(current, bool):
            monkeypatch.setenv(env, "7")
            out = dc._apply_env_overrides(dict(dc.DEFAULT_CONFIG))
            assert out[key] == 7, f"{key}: {env} did not apply"
        else:
            monkeypatch.setenv(env, "0.4242")
            out = dc._apply_env_overrides(dict(dc.DEFAULT_CONFIG))
            assert float(out[key]) == pytest.approx(0.4242), f"{key}: {env} did not apply"
        monkeypatch.delenv(env, raising=False)
        # ...and unsetting it leaves the default in place (no sticky state).
        out = dc._apply_env_overrides(dict(dc.DEFAULT_CONFIG))
        assert out[key] == current, f"{key}: value changed with no env var set"


def test_every_registry_env_var_is_documented_in_env_example():
    text = ENV_EXAMPLE.read_text(encoding="utf-8")
    from tradingagents.default_config import _ENV_OVERRIDES

    key_to_env = {v: k for k, v in _ENV_OVERRIDES.items()}
    missing = [key_to_env[k] for k in REGISTRY if key_to_env[k] not in text]
    assert not missing, f"not documented in .env.example: {missing}"


def test_wired_gates_are_read_somewhere_and_inert_ones_are_read_nowhere():
    """The Status column is a claim about the source, so check it there."""
    wrong = {}
    for key, status in REGISTRY.items():
        hits = _read_sites(key)
        if status == "wired" and not hits:
            wrong[key] = "claimed wired but nothing reads it"
        if status == "inert" and hits:
            wrong[key] = f"claimed inert but read by {hits[:2]}"
    assert not wrong, wrong


def test_the_registry_doc_does_not_claim_coverage_it_does_not_have():
    """The doc covered 40 of the 88 ``enable_*`` keys while titling itself
    "every gate". An over-claim in the file whose whole purpose is to stop
    gates that cannot fire is the same failure in a new place: a reader trusts
    the ABSENCE of a row. The title is narrowed to the families it does cover
    and the engine gates are named as covered elsewhere."""
    text = DOC.read_text(encoding="utf-8")
    title = text.splitlines()[0]
    assert "every gate" not in title.lower(), title
    assert "enable_quant_scorecard" in text, "the excluded engine gates must be named"
    assert "test_quant_scorecard.py" in text, "name where they are covered"


def test_the_engine_gates_the_doc_excludes_really_are_covered_elsewhere():
    """The pointer the doc now makes has to be true."""
    engine_gates = [
        "enable_fundamental_score",
        "enable_technical_score",
        "enable_sentiment_score",
        "enable_news_score",
        "enable_trade_score",
        "enable_regime_score",
        "enable_risk_score",
        "enable_quant_scorecard",
    ]
    for key in engine_gates:
        assert key in dc.DEFAULT_CONFIG, key
        assert key not in REGISTRY, f"{key} is now a registry row - update the doc"
    scorer = (REPO / "tests" / "test_quant_scorecard.py").read_text(encoding="utf-8")
    assert "enable_quant_scorecard" in scorer


def test_the_doc_states_the_whole_enable_surface_and_names_every_excluded_key():
    """The scope paragraph named only the eight score-engine gates while 48
    ``enable_*`` keys have no row. A reader trusts the ABSENCE of a row, so a
    partial exclusion list is the same over-claim in a softer voice: it reads as
    "outside the score engines, everything policy-shaped is registered".

    Both halves are recomputed from DEFAULT_CONFIG and REGISTRY, so stage 2
    cannot add a family and leave the doc behind.
    """
    text = DOC.read_text(encoding="utf-8")
    total = sorted(k for k in dc.DEFAULT_CONFIG if k.startswith("enable_"))
    covered = sorted(k for k in REGISTRY if k.startswith("enable_"))
    missing = [k for k in total if k not in REGISTRY]
    assert f"{len(covered)} of the {len(total)}" in text, (
        f"the doc must state how much of the enable_* surface it covers "
        f"({len(covered)} of {len(total)}); {len(missing)} keys have no row"
    )
    unnamed = [k for k in missing if f"`{k}`" not in text]
    assert not unnamed, (
        f"uncovered enable_* keys the doc never names: {unnamed} - an unlisted "
        "omission reads as 'no such gate'"
    )
