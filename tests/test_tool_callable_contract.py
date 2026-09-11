"""Callable-contract regression tests for agents/utils/analysis_tools.py.

Four verified defects from the implementation-plan defect audit:

* P0-1  ``_cfg_idx`` wrongly carried the ``@tool`` decorator, so it was a
  langchain ``StructuredTool`` (no ``__call__``); ``get_regime_gate_read`` calls
  it directly in Python, so the TypeError was swallowed and the tool ALWAYS
  answered "regime gate read unavailable ... 'StructuredTool' object is not
  callable".
* P0-2  ``get_etf_mechanics`` imported and called the ``@tool``
  ``get_corporate_actions`` from ``moomoo_extra_tools``, so the Distributions
  row silently degraded to "n/a" on every call.
* P0-6  ``_ohlcv`` cached the FAILURE dict under the success key, so a single
  transient vendor error degraded every OHLCV-based tool for that ticker for
  the rest of the process (the absence dict even said ``retryable: True``).
* P0-13 ``get_fixed_income_risk`` passed ``iy / 100.0`` to the duration /
  convexity helpers whose documented contract is a fraction (0.05 = 5%).

The repo-wide gate below is the durable guard for the P0-1/P0-2 class: no
``@tool``-decorated function under ``tradingagents/`` may be CALLED as a plain
Python function. It is scope-aware: a plain module-level ``def`` of the same
name (e.g. ``get_news`` in ``dataflows/alpha_vantage_news.py``) shadows and is
not a violation, and attribute calls (``ctx.get_capital_flow()`` on an
unrelated object) are out of scope.
"""

from __future__ import annotations

import ast
import pathlib
import textwrap

from tradingagents.agents.utils import analysis_tools as at

_TRADINGAGENTS_ROOT = pathlib.Path(__file__).resolve().parents[1] / "tradingagents"


# ---------------------------------------------------------------------------
# Repo-wide gate: never CALL a @tool-decorated function as a plain function
# ---------------------------------------------------------------------------


def _decorator_name(node: ast.AST) -> str | None:
    """Name of a decorator expression (``tool`` for both ``@tool``/``@tool()``)."""
    if isinstance(node, ast.Call):
        return _decorator_name(node.func)
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        return node.attr
    return None


def _module_key(path: pathlib.Path, root: pathlib.Path) -> str:
    rel = path.relative_to(root).with_suffix("")
    return ".".join(part for part in rel.parts if part != "__init__")


def _resolve_module(dotted: str, module_to_file: dict[str, pathlib.Path]) -> pathlib.Path | None:
    """Resolve a dotted module to a file, tolerating a root-relative prefix."""
    if dotted in module_to_file:
        return module_to_file[dotted]
    suffix = "." + dotted
    for key, path in module_to_file.items():
        if suffix.endswith("." + key) and dotted.endswith(key):
            return path
    return None


def find_plain_tool_calls(root: pathlib.Path) -> list[str]:
    """``file:line name`` for every bare-name call of an ``@tool`` function."""
    files = sorted(p for p in root.rglob("*.py") if "__pycache__" not in p.parts)
    trees = {p: ast.parse(p.read_text(encoding="utf-8")) for p in files}
    module_to_file = {_module_key(p, root): p for p in files}

    decorated: dict[pathlib.Path, set[str]] = {}   # file -> @tool def names
    plain_defs: dict[pathlib.Path, set[str]] = {}  # file -> non-@tool bindings
    imports: dict[pathlib.Path, dict[str, tuple[str, str]]] = {}

    for path, tree in trees.items():
        dec: set[str] = set()
        plain: set[str] = set()
        bindings: dict[str, tuple[str, str]] = {}
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                if any(_decorator_name(d) == "tool" for d in node.decorator_list):
                    dec.add(node.name)
                else:
                    plain.add(node.name)
            elif isinstance(node, ast.ClassDef):
                plain.add(node.name)
            elif isinstance(node, ast.ImportFrom):
                if not node.module:
                    continue
                for alias in node.names:
                    if alias.name != "*":
                        bindings[alias.asname or alias.name] = (node.module, alias.name)
        decorated[path], plain_defs[path], imports[path] = dec, plain, bindings

    all_decorated = {name for names in decorated.values() for name in names}
    violations: list[str] = []

    for path, tree in trees.items():
        for node in ast.walk(tree):
            if not (isinstance(node, ast.Call) and isinstance(node.func, ast.Name)):
                continue
            name = node.func.id
            if name in plain_defs[path]:
                continue  # a local plain def shadows the tool name (not a tool)
            binding = imports[path].get(name)
            if binding is not None:
                module, original = binding
                target = _resolve_module(module, module_to_file)
                if target is not None and original in decorated.get(target, ()):
                    violations.append(f"{path}:{node.lineno} {name}")
                continue
            if name in all_decorated:
                violations.append(f"{path}:{node.lineno} {name}")
    return sorted(violations)


def test_no_tool_decorated_function_is_called_as_a_plain_function():
    violations = find_plain_tool_calls(_TRADINGAGENTS_ROOT)
    assert violations == [], (
        "an @tool-decorated function (a StructuredTool, not a callable Python "
        "function) is called directly; call the underlying vendor/route "
        "function instead: " + ", ".join(violations)
    )


def test_gate_flags_the_two_pre_fix_shapes(tmp_path):
    """The gate has teeth: it flags both P0-1 and P0-2 shapes when present."""
    pkg = tmp_path / "tradingagents" / "sub"
    pkg.mkdir(parents=True)
    (pkg / "__init__.py").write_text("", encoding="utf-8")
    (pkg / "tools_mod.py").write_text(
        textwrap.dedent(
            """
            from langchain_core.tools import tool

            @tool
            def get_corporate_actions(ticker: str) -> str:
                return ticker
            """
        ),
        encoding="utf-8",
    )
    (pkg / "caller.py").write_text(
        textwrap.dedent(
            """
            from langchain_core.tools import tool

            from tradingagents.sub.tools_mod import get_corporate_actions

            @tool
            def _cfg_idx() -> str:
                return ""

            def caller():
                return _cfg_idx(), get_corporate_actions("AAPL")
            """
        ),
        encoding="utf-8",
    )

    violations = find_plain_tool_calls(tmp_path / "tradingagents")
    assert any(v.endswith("_cfg_idx") for v in violations), violations
    assert any(v.endswith("get_corporate_actions") for v in violations), violations


def test_gate_ignores_shadowing_plain_defs_and_attribute_calls(tmp_path):
    """A plain local def of a tool name and ``obj.name()`` are not violations."""
    root = tmp_path / "tradingagents"
    root.mkdir(parents=True)
    (root / "__init__.py").write_text("", encoding="utf-8")
    (root / "tools_mod.py").write_text(
        "from langchain_core.tools import tool\n\n\n@tool\ndef get_news(ticker):\n    return ticker\n",
        encoding="utf-8",
    )
    (root / "ok.py").write_text(
        textwrap.dedent(
            """
            def get_news(ticker):
                return ticker


            def caller(stock):
                return get_news("AAPL"), stock.get_news("AAPL")
            """
        ),
        encoding="utf-8",
    )
    assert find_plain_tool_calls(root) == []


# ---------------------------------------------------------------------------
# P0-1: get_regime_gate_read must not report "not callable"
# ---------------------------------------------------------------------------


def test_regime_gate_read_is_not_broken_by_a_tool_wrapped_index_helper(monkeypatch):
    closes = [100.0 + i * 0.05 for i in range(320)]
    fake_ohlcv = lambda ticker, days=320: {  # noqa: E731 - tiny test double
        "dates": [],
        "closes": list(closes),
        "opens": [],
        "highs": [],
        "lows": [],
        "volumes": [],
        "absence": None,
    }
    monkeypatch.setattr(at, "_ohlcv", fake_ohlcv)
    monkeypatch.setattr(at, "_cfg_idx", lambda: "SPY")

    out = at.get_regime_gate_read.invoke({"ticker": "AAPL"})

    assert "not callable" not in out
    assert "regime gate AAPL:" in out
    assert "verdict=" in out


# ---------------------------------------------------------------------------
# P0-6: a failed OHLCV fetch must not poison the run cache
# ---------------------------------------------------------------------------


def test_ohlcv_retries_after_a_failed_fetch(monkeypatch):
    import pandas as pd

    at._clear_ohlcv_cache()
    attempts = {"n": 0}

    def _fail(ticker):
        attempts["n"] += 1
        raise RuntimeError("vendor down")

    monkeypatch.setattr(at, "_load_ohlcv_df", _fail)
    first = at._ohlcv("RETRY")
    assert first["closes"] == []
    assert first["absence"]["retryable"] is True

    frame = pd.DataFrame(
        {
            "Date": ["2026-09-08", "2026-09-09"],
            "Close": [10.0, 11.0],
            "High": [10.5, 11.5],
            "Low": [9.5, 10.5],
            "Open": [10.0, 11.0],
            "Volume": [100.0, 200.0],
        }
    )
    monkeypatch.setattr(at, "_load_ohlcv_df", lambda ticker: frame)
    second = at._ohlcv("RETRY")

    assert second["closes"] == [10.0, 11.0]
    assert attempts["n"] == 1  # only the first (failed) call hit the vendor seam
    at._clear_ohlcv_cache()


# ---------------------------------------------------------------------------
# P0-2: get_etf_mechanics must read distributions from the vendor route
# ---------------------------------------------------------------------------


def test_etf_mechanics_renders_distributions_from_the_vendor_route(monkeypatch):
    class _Ticker:
        info = {"navPrice": 100.0, "regularMarketPrice": 101.0}

    monkeypatch.setattr("yfinance.Ticker", lambda ticker: _Ticker())
    monkeypatch.setattr(
        at,
        "route_to_vendor",
        lambda method, *args, **kwargs: "## Corporate Actions\n- dividend $0.10 2026-06-15",
    )

    out = at.get_etf_mechanics.invoke({"ticker": "IGV"})

    assert "- Distributions: ## Corporate Actions" in out
    assert "Distributions: n/a" not in out


# ---------------------------------------------------------------------------
# P0-13: the indicated yield is a fraction, not a percent
# ---------------------------------------------------------------------------


def test_fixed_income_risk_passes_the_fraction_yield(monkeypatch):
    from tradingagents.strategies.fixed_income import (
        bond_convexity,
        indicated_yield,
        macaulay_duration,
        modified_duration,
    )

    fundamentals = "Dividend Rate: 2.00\nCurrent Price: 25.00"
    monkeypatch.setattr(
        "tradingagents.dataflows.interface.route_to_vendor",
        lambda method, *args, **kwargs: fundamentals,
    )

    out = at.get_fixed_income_risk.invoke({"ticker": "PFD", "years": 5})

    iy = indicated_yield(2.0, 25.0)
    cashflows = [{"t": 5.0, "amount": 25.0 * 5}]
    mac = macaulay_duration(cashflows, iy)
    mod = modified_duration(mac, iy)
    convexity = bond_convexity(cashflows, iy)
    percent_mod = modified_duration(mac, iy / 100.0)
    percent_convexity = bond_convexity(cashflows, iy / 100.0)

    # The fixture must distinguish the two contracts at the rendered precision,
    # otherwise the assertions below are vacuous.
    assert f"{mod:.2f}" != f"{percent_mod:.2f}"
    assert f"{convexity:.2f}" != f"{percent_convexity:.2f}"

    assert f"indicated_yield={iy:.2%}" in out
    assert f"  modified={mod:.2f}" in out
    assert f"  convexity={convexity:.2f}" in out
    assert f"  modified={percent_mod:.2f}" not in out
    assert f"  convexity={percent_convexity:.2f}" not in out


# ---------------------------------------------------------------------------
# P1 look-ahead: get_insider_activity forwards curr_date to the vendor
# ---------------------------------------------------------------------------


def test_insider_activity_forwards_curr_date_to_the_vendor(monkeypatch):
    def _stub(ticker, curr_date=None):
        return f"insider window anchored on {curr_date or 'now'}"

    monkeypatch.setattr("tradingagents.dataflows.finnhub.get_insider_activity_finnhub", _stub)

    dated = at.get_insider_activity.invoke({"ticker": "AAPL", "curr_date": "2025-03-14"})
    undated = at.get_insider_activity.invoke({"ticker": "AAPL"})

    assert "anchored on 2025-03-14" in dated
    assert "anchored on now" in undated


def test_insider_activity_window_ends_on_the_passed_date(monkeypatch):
    """End-to-end: the real vendor seam accepts curr_date as the 2nd positional."""
    import tradingagents.dataflows.finnhub as finnhub

    class _Client:
        def __init__(self):
            self.calls = []

        def stock_insider_sentiment(self, symbol, _from=None, to=None):
            self.calls.append((_from, to))
            return {"data": [{"year": 2026, "month": 8, "change": 5.0, "mspr": 1.0}]}

    client = _Client()
    monkeypatch.setattr(finnhub, "_client", lambda: client)

    out = at.get_insider_activity.invoke({"ticker": "AAPL", "curr_date": "2026-09-10"})

    assert client.calls, "the vendor client must have been called"
    assert client.calls[0][1] == "2026-09-10"
    assert "Insider Sentiment" in out
