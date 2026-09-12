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
    "enable_preopen_depth": "wired",
    "risk_audit_enabled": "wired",
    "regime_state_enable": "wired",
    "vol_cap_enable": "wired",
    "enable_sector_multifactor": "wired",
    "enable_sector_industry": "wired",
    "enable_sector_breadth": "wired",
    "enable_sector_eodhd_constituents": "wired",
    "enable_spread_estimator": "wired",
    "enable_book_risk_sizing": "wired",
    "enable_conformal_bands": "wired",
    "enable_return_decomposition": "wired",
    "enable_text_factors": "wired",
    "enable_bocpd": "wired",
    "backtest_limit_threshold": "wired",
    "backtest_volume_participation": "wired",
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
    # declared but read by nothing (see registry section 3)
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
    """{key: (env var, status)} from the registry tables (sections 1-3)."""
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
    access idiom (``cfg.get("key")``, ``config["key"]``, ``_flag("key")``, a
    comparison, a membership test). Root-level entry points (``batch.py``) count
    too - a gate read there is still a gate.
    """
    pattern = re.compile(
        r"""(?:\.get\(|\[|_flag\(|==|!=|in\s*\(|in\s*\{|\bor\b\s*)\s*["']"""
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
