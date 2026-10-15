"""The ``.env`` shadow audit - an exported ``TRADINGAGENTS_*`` value wins over the file.

``load_dotenv`` defaults to ``override=False``, so the process environment is the
higher-priority source: python-dotenv's README documents that order, pydantic-settings
states "environment variables will always take priority over values loaded from a dotenv
file", and 12factor.net III requires config to live in the environment. Correct - and
invisible, and the exported set on this machine has drifted: a 13-name vs 15-name risk
basket moves the book-CVaR GATE INPUT, and a flipped decider gate changed a tree's verdict
battery from three files to four with nothing in the report saying so. So
``tradingagents.__init__`` names the surviving keys once, at import.

The contract these tests pin: names are reported, values never are (the values in this
file are usually secrets), the engine's own config family is the only family audited, a
key the file does not declare is not a shadow, and the audit runs AFTER the three forced
output-token caps - a cap re-forced from the file is not a shadow.
"""

import os
import subprocess
import sys
from pathlib import Path

from tradingagents import env_shadow_keys, env_shadow_warning

FILE_DECLARED = {
    "TRADINGAGENTS_RISK_BASKET_TICKERS": "SPY,GLD,NVDA",
    "TRADINGAGENTS_ENABLE_NOUL_DECIDER": "false",
    "TRADINGAGENTS_MAX_OUTPUT_TOKENS": "32000",
    "TRADINGAGENTS_ENABLE_FACT_LAYER": "true",
    "ALPACA_API_KEY": "file-alpaca",
    "TRADINGAGENTS_VALUELESS": None,
}


def test_a_matching_export_is_not_shadowed():
    environ = {"TRADINGAGENTS_RISK_BASKET_TICKERS": "SPY,GLD,NVDA"}
    assert env_shadow_keys(FILE_DECLARED, environ) == []


def test_a_differing_export_is_named():
    environ = {"TRADINGAGENTS_RISK_BASKET_TICKERS": "SPY,GLD"}
    assert env_shadow_keys(FILE_DECLARED, environ) == ["TRADINGAGENTS_RISK_BASKET_TICKERS"]


def test_a_flipped_gate_is_named():
    environ = {"TRADINGAGENTS_ENABLE_NOUL_DECIDER": "true"}
    assert env_shadow_keys(FILE_DECLARED, environ) == ["TRADINGAGENTS_ENABLE_NOUL_DECIDER"]


def test_an_export_the_file_does_not_declare_is_not_a_shadow():
    assert env_shadow_keys(FILE_DECLARED, {"TRADINGAGENTS_BRAND_NEW_KEY": "1"}) == []


def test_a_key_only_in_the_file_is_not_a_shadow():
    assert env_shadow_keys(FILE_DECLARED, {}) == []


def test_a_valueless_key_line_is_not_a_shadow():
    # `KEY` with no `=` is ignored by load_dotenv, so the export is the only value.
    assert env_shadow_keys(FILE_DECLARED, {"TRADINGAGENTS_VALUELESS": "x"}) == []


def test_only_the_engine_config_family_is_audited():
    environ = {"ALPACA_API_KEY": "exported-alpaca", "TRADINGAGENTS_ENABLE_FACT_LAYER": "false"}
    assert env_shadow_keys(FILE_DECLARED, environ) == ["TRADINGAGENTS_ENABLE_FACT_LAYER"]


def test_the_order_is_stable():
    environ = {
        "TRADINGAGENTS_MAX_OUTPUT_TOKENS": "1",
        "TRADINGAGENTS_ENABLE_NOUL_DECIDER": "true",
    }
    assert env_shadow_keys(FILE_DECLARED, environ) == [
        "TRADINGAGENTS_ENABLE_NOUL_DECIDER",
        "TRADINGAGENTS_MAX_OUTPUT_TOKENS",
    ]


def test_no_shadow_is_no_warning():
    assert env_shadow_warning([]) is None


def test_the_warning_names_keys_and_never_a_value():
    environ = {"TRADINGAGENTS_RISK_BASKET_TICKERS": "SPY"}
    shadowed = env_shadow_keys(FILE_DECLARED, environ)
    msg = env_shadow_warning(shadowed)
    assert msg is not None
    assert "TRADINGAGENTS_RISK_BASKET_TICKERS" in msg
    assert "SPY,GLD,NVDA" not in msg and "SPY" not in msg
    assert msg.count(chr(10)) == 0  # a single log line


def test_the_warning_caps_the_listing_and_counts_the_rest():
    names = [f"TRADINGAGENTS_KEY_{i}" for i in range(9)]
    msg = env_shadow_warning(names)
    assert msg is not None
    assert "TRADINGAGENTS_KEY_0" in msg and "TRADINGAGENTS_KEY_5" in msg
    assert "TRADINGAGENTS_KEY_6" not in msg
    assert "(+3 more)" in msg


def test_the_import_names_a_shadowed_key_and_prints_no_value(tmp_path):
    """The audit is wired at import: a fresh interpreter whose cwd holds the .env."""
    (tmp_path / ".env").write_text(
        "TRADINGAGENTS_SHADOW_PROBE=file-value\nOPENROUTER_API_KEY=file-secret\n",
        encoding="utf-8",
    )
    repo_root = Path(__file__).resolve().parents[1]
    env = {
        **os.environ,
        "PYTHONPATH": str(repo_root),
        "TRADINGAGENTS_SHADOW_PROBE": "exported-value",
    }
    proc = subprocess.run(
        [sys.executable, "-c", "import tradingagents"],
        capture_output=True,
        text=True,
        cwd=str(tmp_path),
        env=env,
    )
    assert proc.returncode == 0, proc.stderr
    assert "TRADINGAGENTS_SHADOW_PROBE" in proc.stderr
    assert "exported-value" not in proc.stderr
    assert "file-value" not in proc.stderr and "file-secret" not in proc.stderr
