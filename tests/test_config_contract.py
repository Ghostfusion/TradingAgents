"""Contract tests for ``DEFAULT_CONFIG`` and the TRADINGAGENTS_* env overlay (P0-7).

``_coerce`` types each override by the *existing* default value. A target key
absent from ``DEFAULT_CONFIG`` leaves it with no type reference, so the raw env
string is stored verbatim — ``TRADINGAGENTS_ENABLE_PRE_MARKET_REVIEW=false``
became the truthy string ``"false"`` and the feature the user disabled still
ran.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from tradingagents.default_config import (
    _ENV_OVERRIDES,
    DEFAULT_CONFIG,
    _validate_env_override_targets,
)

_REPO_ROOT = Path(__file__).resolve().parents[1]

# The two P0-7 flags: opt-in features whose env override row had no base key.
_OPT_IN_FLAGS = {
    "TRADINGAGENTS_ENABLE_PIT_REGISTRY": "enable_pit_registry",
    "TRADINGAGENTS_ENABLE_PRE_MARKET_REVIEW": "enable_pre_market_review",
}

_PROBE = (
    "import json;"
    "from tradingagents.default_config import DEFAULT_CONFIG as C;"
    "print('RESULT:' + json.dumps({"
    "'enable_pit_registry': [C['enable_pit_registry'], type(C['enable_pit_registry']).__name__,"
    " bool(C['enable_pit_registry'])],"
    "'enable_pre_market_review': [C['enable_pre_market_review'],"
    " type(C['enable_pre_market_review']).__name__, bool(C['enable_pre_market_review'])]}))"
)


def _probe_config(extra_env: dict[str, str], cwd: Path) -> dict:
    """Import DEFAULT_CONFIG in a fresh interpreter and report the two flags.

    ``cwd`` points at an empty temp dir so the package's ``.env`` autoload does
    not shadow the caller-controlled environment (the repo's own ``.env`` sets
    several TRADINGAGENTS_* flags); PYTHONPATH keeps the package importable.
    """
    env = {k: v for k, v in os.environ.items() if not k.startswith("TRADINGAGENTS_")}
    env["PYTHONPATH"] = str(_REPO_ROOT)
    env.update(extra_env)
    proc = subprocess.run(
        [sys.executable, "-c", _PROBE],
        cwd=cwd,
        env=env,
        capture_output=True,
        text=True,
        timeout=180,
    )
    assert proc.returncode == 0, f"probe failed:\n{proc.stderr}"
    line = next(ln for ln in proc.stdout.splitlines() if ln.startswith("RESULT:"))
    return json.loads(line[len("RESULT:") :])


@pytest.mark.unit
class TestEnvOverrideTargets:
    def test_every_override_target_exists_in_default_config(self):
        missing = sorted(
            (env_var, key)
            for env_var, key in _ENV_OVERRIDES.items()
            if key not in DEFAULT_CONFIG
        )
        assert not missing, (
            f"_ENV_OVERRIDES rows with no DEFAULT_CONFIG key (their env value "
            f"would be stored as a raw string): {missing}"
        )

    @pytest.mark.parametrize(
        "env_var,key", sorted(_OPT_IN_FLAGS.items()), ids=["pit_registry", "pre_market_review"]
    )
    def test_opt_in_flag_is_a_real_bool_in_default_config(self, env_var, key):
        # Type contract: whether the value comes from the base default or from
        # an env override, _coerce must yield a bool (never a raw string).
        assert isinstance(DEFAULT_CONFIG[key], bool)

    def test_missing_target_raises_naming_env_var_and_key(self):
        config = dict(DEFAULT_CONFIG)
        config.pop("enable_pit_registry")
        with pytest.raises(ValueError) as excinfo:
            _validate_env_override_targets(config)
        message = str(excinfo.value)
        assert "TRADINGAGENTS_ENABLE_PIT_REGISTRY" in message
        assert "enable_pit_registry" in message


@pytest.mark.unit
class TestEnvBoolCoercion:
    def test_env_false_is_a_real_false_bool(self, tmp_path):
        flags = _probe_config(dict.fromkeys(_OPT_IN_FLAGS, "false"), tmp_path)
        for key in _OPT_IN_FLAGS.values():
            value, type_name, truthy = flags[key]
            assert value is False, f"{key} stored {value!r} instead of a real False"
            assert type_name == "bool"
            assert truthy is False

    def test_env_true_is_a_real_true_bool(self, tmp_path):
        value, type_name = _probe_config(
            {"TRADINGAGENTS_ENABLE_PIT_REGISTRY": "true"}, tmp_path
        )["enable_pit_registry"][:2]
        assert value is True
        assert type_name == "bool"
