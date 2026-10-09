"""Console entry point for the ``tradingagents`` script.

The script used to be declared as ``cli.main:app``, but ``cli`` is a top-level
package name this project does not own: two other distributions in the same
site-packages ship one - ``vibe_trading_ai`` (``vibe-trading = cli:main``) and
``stringzilla`` - and an editable install of this repo maps ``cli`` through a
meta-path finder that is consulted only AFTER the ordinary path finder. So the
console script resolved ``cli`` to another project's package and every
invocation died with ``ImportError: cannot import name 'app' from 'cli.main'``
(2026-10-09).

Loading the app from a module inside the uniquely-named ``tradingagents``
package removes that ambiguity: the checkout root goes first on ``sys.path``, so
``cli`` here is always this repo's own package, whatever else is installed
alongside it.
"""

from __future__ import annotations

import pathlib
import sys


def load_app():
    """This repo's Typer ``app``, resolved past any foreign ``cli`` package.

    The checkout root is moved to the FRONT of ``sys.path`` - not merely added
    if absent - because the failure being fixed is one of ORDER: a foreign
    ``cli`` sat ahead of the repo on the path.
    """
    root = str(pathlib.Path(__file__).resolve().parents[1])
    if root in sys.path:
        sys.path.remove(root)
    sys.path.insert(0, root)
    from cli.main import app

    return app


def main() -> None:
    """Run the interactive CLI - the ``tradingagents`` console script's target."""
    load_app()()
