"""The suite must never inherit the operator's ``.env`` configuration.

``tradingagents/__init__.py`` loads a developer's ``.env`` into ``os.environ``
at package import, and ``DEFAULT_CONFIG`` is the shipped dict **with** those
``TRADINGAGENTS_*`` values folded in. ``reset_config()`` restored that ambient
dict, so a plain report-write test ran whatever the operator's machine had
enabled: ``tests/test_reporting.py`` calls ``write_report_tree(config=None)``,
the run-card engines were live, and every write resolved a nine-name peer
universe through the vendor chain (``resolve_peer_universe`` -> ``fetch_ticker``
-> Tiingo retry backoff).  Measured 2026-09-30: that module consumed two
30-minute pytest bounds instead of finishing in ~20 s.
"""

from __future__ import annotations

import pytest

from tradingagents import default_config as default_config_module
from tradingagents.dataflows import config as config_module

pytestmark = pytest.mark.timeout(600)


def test_reset_config_discards_the_ambient_env_for_a_gate(monkeypatch):
    """A gate the machine's ``.env`` switched on must be off after a reset.

    The process fallback is forced to look like this developer's machine (a card
    engine enabled in ``.env``); the reset has to discard that, not copy it.
    """
    monkeypatch.setitem(
        default_config_module.DEFAULT_CONFIG, "enable_fundamental_score", True
    )
    config_module.set_config({"enable_fundamental_score": True})

    config_module.reset_config()

    assert config_module.get_config()["enable_fundamental_score"] is False
    assert default_config_module.SHIPPED_DEFAULTS["enable_fundamental_score"] is False


def test_reset_config_leaves_no_key_differing_from_the_shipped_defaults(monkeypatch):
    """No ambient override may survive a reset - gates, models and paths alike."""
    monkeypatch.setitem(default_config_module.DEFAULT_CONFIG, "llm_provider", "ambient")
    config_module.set_config({"llm_provider": "ambient"})

    config_module.reset_config()

    drifted = sorted(
        key
        for key, value in config_module.get_config().items()
        if value != default_config_module.SHIPPED_DEFAULTS.get(key)
    )
    assert not drifted, f"ambient values survived reset_config(): {drifted}"
