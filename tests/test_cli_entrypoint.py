"""The ``tradingagents`` console script must load THIS repo's ``cli`` package.

``cli`` is a top-level name two other distributions in this environment also
ship - ``vibe_trading_ai`` declares ``vibe-trading = cli:main`` and
``stringzilla`` ships ``cli/split.py`` - and an editable install of this repo
maps ``cli`` through a meta-path finder that is consulted only AFTER the
ordinary path finder. The script declared ``cli.main:app``, so it resolved to
another project's ``cli`` and every invocation died with
``ImportError: cannot import name 'app' from 'cli.main'`` (2026-10-09).

Hermetic: no network, no install - the shadowing package is a temp directory.
"""

import os
import pathlib
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from tradingagents import cli_entry  # noqa: E402

REPO = pathlib.Path(cli_entry.__file__).resolve().parents[1]


def test_the_launcher_puts_this_repos_cli_ahead_of_a_shadowing_package(tmp_path, monkeypatch):
    decoy = tmp_path / "cli"
    decoy.mkdir()
    (decoy / "__init__.py").write_text("# another project's cli\n", encoding="utf-8")
    (decoy / "main.py").write_text("def main():\n    return 'not ours'\n", encoding="utf-8")
    # The checkout is on the path already, but the foreign `cli` sits ahead of it
    # - which is the whole defect. The launcher has to win on ORDER.
    monkeypatch.syspath_prepend(str(REPO))
    monkeypatch.syspath_prepend(str(decoy))
    # Drop any cached `cli` so the resolution under test actually happens.
    for name in [m for m in list(sys.modules) if m == "cli" or m.startswith("cli.")]:
        monkeypatch.delitem(sys.modules, name)

    app = cli_entry.load_app()

    import cli

    assert pathlib.Path(cli.__file__).resolve().parent == REPO / "cli"
    assert app.info.name == "TradingAgents"  # the repo's app, not the decoy's
