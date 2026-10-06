"""`docs/api_reference.md` §1.1 claims "(complete)" - this keeps that true.

The table is generated from the code, but a generator someone forgets to re-run
is not a guarantee. This test is: it re-derives the env->config surface from
`tradingagents/default_config.py` and asserts the document lists exactly it.

It failed before the 2026-09-21 fix: the table documented 165 of 258 override
rows, so 95 knobs - the whole debate-model block, `backtest_*`,
`enable_decision_guardrail`, `enable_tuner`, `llm_tier_*`, `monitor_*`,
`knife_*` and more - were absent from a table advertising completeness. The
table also carried ~15 duplicated rows, three mangled rows, an unescaped `|`
that split a row into four cells, and a row for
`TRADINGAGENTS_ENABLE_ALPHA_PROFILE` -> `enable_alpha_profile`, an env var and
a config key that exist in NO file (`alpha_profile` is a *report* key in
`scripts/strategy_quality_report.py`). Every one of those is now a failure.
"""

from __future__ import annotations

import ast
import re
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
DOC = REPO / "docs" / "api_reference.md"
CONFIG = REPO / "tradingagents" / "default_config.py"

pytestmark = pytest.mark.timeout(120)


def _code_surface() -> dict[str, str]:
    """Every env var that reaches the config, mapped to its key.

    Two mechanisms, and the union is the truth: `_ENV_OVERRIDES` (the bulk) and
    a literal `os.getenv("TRADINGAGENTS_...", fallback)` inside the
    `DEFAULT_CONFIG` dict (results_dir, data_cache_dir, the verifier model, ...).
    """
    source = CONFIG.read_text(encoding="utf-8")
    surface: dict[str, str] = {}
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.Assign) and any(
            getattr(t, "id", None) == "_ENV_OVERRIDES" for t in node.targets
        ):
            assert isinstance(node.value, ast.Dict)
            for k, v in zip(node.value.keys, node.value.values, strict=True):
                assert isinstance(k, ast.Constant) and isinstance(v, ast.Constant)
                surface[str(k.value)] = str(v.value)
    for m in re.finditer(
        r'"([a-z_][a-z0-9_]*)"\s*:\s*(?:int\()?\s*os\.(?:getenv|environ\.get)\(\s*"([A-Z_]+)"',
        source,
    ):
        surface.setdefault(m.group(2), m.group(1))
    return surface


def _doc_rows() -> list[tuple[int, str, str, int]]:
    """(line_no, env, config_key, cell_count) for every row of the §1.1 table."""
    lines = DOC.read_text(encoding="utf-8").splitlines()
    start = next(i for i, ln in enumerate(lines) if ln.startswith("### 1.1"))
    end = next(
        i
        for i in range(start + 1, len(lines))
        if lines[i].startswith("### ") or lines[i].startswith("## ")
    )
    rows: list[tuple[int, str, str, int]] = []
    for i in range(start, end):
        ln = lines[i]
        if not ln.startswith("|"):
            continue
        cells = [c.strip() for c in ln.strip().strip("|").split("|")]
        if cells[0] in ("Env var", "---") or set(cells[0]) <= {"-", " "}:
            continue
        rows.append((i + 1, cells[0].strip("`"), cells[1].strip("`"), len(cells)))
    return rows


def test_the_table_lists_every_env_var_the_config_reads():
    """The heading says "(complete)" - this is what that has to mean."""
    surface = _code_surface()
    documented = {env for _, env, _, _ in _doc_rows()}
    missing = sorted(set(surface) - documented)
    assert not missing, (
        f"docs/api_reference.md §1.1 claims to be complete but omits {len(missing)} "
        f"env vars the config reads: {missing}"
    )
    extra = sorted(documented - set(surface))
    assert not extra, (
        f"docs/api_reference.md §1.1 documents env vars that no code reads: {extra}"
    )


def test_every_row_maps_the_env_var_to_the_key_the_code_maps_it_to():
    """A row naming the wrong config key is worse than a missing row."""
    surface = _code_surface()
    wrong = [
        f"line {n}: {env} -> {key} (code says {surface[env]})"
        for n, env, key, _ in _doc_rows()
        if env in surface and key != surface[env]
    ]
    assert not wrong, "docs/api_reference.md §1.1 has mis-keyed rows:\n" + "\n".join(wrong)


def test_every_row_has_the_same_cell_count():
    """An unescaped `|` in a note splits a row and silently drops a column."""
    bad = {n: c for n, _, _, c in _doc_rows() if c != 3}
    assert not bad, f"§1.1 rows with a non-3 cell count (line -> count): {bad}"


def test_no_duplicate_env_var_rows():
    seen: dict[str, int] = {}
    dupes: dict[str, list[int]] = {}
    for n, env, _, _ in _doc_rows():
        if env in seen:
            dupes.setdefault(env, [seen[env]]).append(n)
        else:
            seen[env] = n
    assert not dupes, f"§1.1 lists the same env var twice: {dupes}"


def test_the_generator_can_read_the_defaults_it_prints():
    """A row saying ``default `?` `` is the generator's fallback for a key its AST
    scan could not find - and it reads as a default, not as a miss.

    This caught a live defect (2026-10-06): the scan looked only for a bare
    ``DEFAULT_CONFIG = <dict literal>``, but the config is built as
    ``DEFAULT_CONFIG = _apply_env_overrides(dict(SHIPPED_DEFAULTS))`` - a dict
    behind a CALL - so it parsed **0** keys and every row fell back to whatever
    note the doc already carried. Three rows were shipped stating a ``?``
    default because of it: both decider gates and ``enable_metric_authority``.
    """
    sys.path.insert(0, str(REPO / "scripts"))
    import gen_api_reference_table as gen

    parsed = gen.config_defaults()
    assert parsed, "the §1.1 generator parsed no defaults at all - the shape moved"
    unreadable = sorted(k for k in _code_surface().values() if k not in parsed)
    assert not unreadable, (
        f"the §1.1 generator cannot read {len(unreadable)} config defaults, so their "
        f"notes would print the `?` fallback: {unreadable}"
    )


def test_no_row_states_an_unknown_default():
    lines = DOC.read_text(encoding="utf-8").splitlines()
    bad = [
        f"line {n}: {ln.split('|')[1].strip()}"
        for n, ln in enumerate(lines, 1)
        if ln.startswith("| `TRADINGAGENTS_") and "default `?`" in ln
    ]
    assert not bad, (
        "docs/api_reference.md §1.1 rows stating an unknown default - an "
        "unstated default is honest, a `?` default is a wrong one:\n" + "\n".join(bad)
    )
