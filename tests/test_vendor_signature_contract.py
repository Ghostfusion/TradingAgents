"""S4 gate: every registered vendor adapter can serve the router's call.

``route_to_vendor`` forwards the caller's positional/keyword arguments verbatim
to ``VENDOR_METHODS[method][vendor]``. The callers are the ``@tool`` wrappers in
``tradingagents/agents/utils/``, so the union of their
``route_to_vendor("<method>", ...)`` call sites *is* the adapter contract. A
registered adapter whose signature cannot bind that call raises ``TypeError``
inside the router's generic ``except``; the router logs it and advances, so the
configured vendor is a chain entry that silently does not exist (P0-11).

The gate derives each method's call shape from the wrappers' AST (arity +
keyword names) and checks two things per adapter:

1. the signature binds the call (arity / keyword names);
2. each argument keeps its role - symbol / date / frequency - so a vendor that
   takes ``(symbol, start_date, end_date)`` is flagged when the router passes a
   reporting frequency in the second slot.

Roles come from the parameter-name conventions shared across the vendor modules
(every wrapper annotation is a plain ``str``, so names are the only contract
signal available). Unknown names are not checked - this is a compatibility
screen for the router contract, not a type checker.
"""

from __future__ import annotations

import ast
import inspect
import pathlib
from unittest import mock

from tradingagents.dataflows.interface import VENDOR_METHODS

_REPO_ROOT = pathlib.Path(__file__).resolve().parents[1]
_WRAPPER_DIR = _REPO_ROOT / "tradingagents" / "agents" / "utils"

# Registered methods with no ``route_to_vendor`` call site in the tool wrappers
# (they are not exposed as agent tools, so nothing derives a shape for them).
# Kept explicit so a newly registered method without a call site fails the
# coverage test instead of being silently skipped.
_METHODS_WITHOUT_WRAPPERS = {
    "get_basic_financials",
    "get_company_peers",
    "get_insider_activity",
    "get_exchange_symbols",
}

_FREQ_PARAMS = {
    "freq", "frequency", "interval", "period", "timeframe", "granularity",
    "resolution", "resample_freq",
}


def _role(name: str | None) -> str | None:
    """Coarse argument role for a parameter name, or None when unknown."""
    if not name:
        return None
    low = name.lower()
    if "date" in low or low.endswith("_days") or low in {"day", "days", "curr", "as_of", "asof"}:
        return "date"
    if low in _FREQ_PARAMS or "freq" in low:
        return "freq"
    if "ticker" in low or "symbol" in low or low == "sym":
        return "symbol"
    return None


def _wrapper_call_shapes() -> dict[str, dict[int, list]]:
    """method -> {positional arity: ([param names], {kwarg name: param})}.

    Scans every ``@tool`` wrapper for ``route_to_vendor`` calls, including the
    ``_cached_news(..., route_to_vendor, "<method>", ...)`` indirection. A
    positional argument is recorded by name only when it resolves to a
    parameter of the enclosing wrapper; literals and locals become None and are
    skipped by the role check.
    """
    shapes: dict[str, dict[int, list]] = {}

    def merge(method: str, positional: list, keywords: dict) -> None:
        by_arity = shapes.setdefault(method, {})
        current = by_arity.get(len(positional))
        if current is None:
            by_arity[len(positional)] = [list(positional), dict(keywords)]
            return
        for index, name in enumerate(positional):
            if current[0][index] is None:
                current[0][index] = name
        current[1].update(keywords)

    for path in sorted(_WRAPPER_DIR.glob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for fn in ast.walk(tree):
            if not isinstance(fn, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            params = [arg.arg for arg in fn.args.args]
            for call in ast.walk(fn):
                if not isinstance(call, ast.Call) or not call.args:
                    continue
                if isinstance(call.func, ast.Name) and call.func.id == "route_to_vendor":
                    offset = 0
                else:
                    offset = next(
                        (i + 1 for i, arg in enumerate(call.args)
                         if isinstance(arg, ast.Name) and arg.id == "route_to_vendor"),
                        None,
                    )
                if offset is None or len(call.args) <= offset:
                    continue
                method_node = call.args[offset]
                if not (isinstance(method_node, ast.Constant)
                        and isinstance(method_node.value, str)):
                    continue
                positional = [
                    arg.id if isinstance(arg, ast.Name) and arg.id in params else None
                    for arg in call.args[offset + 1:]
                ]
                keywords = {
                    kw.arg: (kw.value.id if isinstance(kw.value, ast.Name)
                             and kw.value.id in params else None)
                    for kw in call.keywords if kw.arg
                }
                merge(method_node.value, positional, keywords)
    return shapes


def _adapter_violations(method: str, vendor: str, impl, shapes: dict) -> list[str]:
    """Contract violations for one registered adapter, formatted for a failure."""
    fn = impl[0] if isinstance(impl, list) else impl
    try:
        signature = inspect.signature(fn)
    except (TypeError, ValueError):
        return []
    params = [
        p.name for p in signature.parameters.values()
        if p.kind in (p.POSITIONAL_ONLY, p.POSITIONAL_OR_KEYWORD)
    ]
    problems = []
    for arity, (names, keywords) in sorted(shapes.items()):
        try:
            signature.bind(*([None] * arity), **dict.fromkeys(keywords))
        except TypeError as exc:
            problems.append(
                f"{method}/{vendor}: router calls with {arity} positional + "
                f"{sorted(keywords)} keyword arg(s), but {fn.__name__}{signature} "
                f"cannot accept them ({exc})"
            )
            continue
        for position, canonical_name in enumerate(names):
            if position >= len(params):
                continue
            expected = _role(canonical_name)
            actual = _role(params[position])
            if expected and actual and expected != actual:
                problems.append(
                    f"{method}/{vendor}: call-site argument {position} is "
                    f"'{canonical_name}' ({expected}) but {fn.__name__} binds "
                    f"'{params[position]}' ({actual})"
                )
    return problems


def test_every_registered_method_has_a_derived_call_shape():
    shapes = _wrapper_call_shapes()

    # Guard against the AST walk silently finding nothing (a vacuous gate).
    assert _role(shapes["get_balance_sheet"][3][0][1]) == "freq"
    assert _role(shapes["get_global_news"][3][0][0]) == "date"
    missing = set(VENDOR_METHODS) - set(shapes)
    assert missing <= _METHODS_WITHOUT_WRAPPERS, (
        f"registered methods with no route_to_vendor call site: {sorted(missing)}"
    )


def test_every_vendor_adapter_accepts_the_router_call():
    shapes = _wrapper_call_shapes()
    problems = []
    for method, implementations in VENDOR_METHODS.items():
        method_shapes = shapes.get(method)
        if not method_shapes:
            continue
        for vendor, impl in implementations.items():
            problems.extend(_adapter_violations(method, vendor, impl, method_shapes))
    assert problems == []


def test_gate_flags_mismatched_adapters():
    """Self-test: the checker reports arity and role mismatches, not just []."""
    shapes = _wrapper_call_shapes()

    def balance_sheet_with_dates(symbol, start_date, end_date):
        return ""

    def short_fundamentals(symbol):
        return ""

    def compatible_balance_sheet(symbol, freq, curr_date):
        return ""

    problems = _adapter_violations(
        "get_balance_sheet", "bogus", balance_sheet_with_dates, shapes["get_balance_sheet"]
    )
    assert any("start_date" in problem and "(date)" in problem for problem in problems)

    problems = _adapter_violations(
        "get_fundamentals", "bogus", short_fundamentals, shapes["get_fundamentals"]
    )
    assert any("cannot accept" in problem for problem in problems)

    assert _adapter_violations(
        "get_balance_sheet", "bogus", compatible_balance_sheet, shapes["get_balance_sheet"]
    ) == []


def test_gdelt_global_news_entry_serves_through_the_router():
    """The registered gdelt adapter for ``get_global_news`` is reachable."""
    from tradingagents.dataflows.config import set_config
    from tradingagents.dataflows.interface import route_to_vendor
    from tradingagents.dataflows.vendor_cache import vendor_cache

    articles = [{
        "title": "Fed holds rates steady", "url": "https://example.com/fed",
        "source": "example.com/business", "seendate": "20260910T120000Z",
        "tone": "5.2,1.0,2.0,3.0",
    }]
    set_config({"data_vendors": {"news_data": "gdelt"}})
    vendor_cache.clear()
    with mock.patch("tradingagents.dataflows.gdelt._gdelt_get", return_value=articles):
        out = route_to_vendor("get_global_news", "2026-09-10", 3, 5)

    assert "## Global Macro News" in out
    assert "Fed holds rates steady" in out
    assert "tone: avg=5.2" in out


def test_tiingo_fundamentals_entry_serves_through_the_router():
    """The registered tiingo adapter for ``get_fundamentals`` is reachable and
    the NEWEST reported period wins (Tiingo returns statements newest-first)."""
    from tradingagents.dataflows.config import set_config
    from tradingagents.dataflows.interface import route_to_vendor
    from tradingagents.dataflows.statement_parsing import _canonicalize
    from tradingagents.dataflows.vendor_cache import vendor_cache

    codes = {
        "incomeStatement": ("revenue", 7.0, 3.0),
        "balanceSheet": ("totalAssets", 70.0, 30.0),
        "cashFlow": ("ncfo", 17.0, 13.0),
    }

    def payload(path, params=None):
        statement = (params or {}).get("statementType")
        code, newest, older = codes[statement]
        return [
            {"date": "2026-06-27", "year": 2026, "quarter": 3,
             "statementData": {statement: [{"dataCode": code, "value": newest}]}},
            {"date": "2026-03-28", "year": 2026, "quarter": 2,
             "statementData": {statement: [{"dataCode": code, "value": older}]}},
        ]

    set_config({"data_vendors": {"fundamental_data": "tiingo"}})
    vendor_cache.clear()
    with mock.patch("tradingagents.dataflows.tiingo._tiingo_get", side_effect=payload):
        out = route_to_vendor("get_fundamentals", "ZZSIGCONTRACT", "2026-09-10")

    canonical = _canonicalize(out)
    assert canonical["revenue"] == 7.0
    assert canonical["total_assets"] == 70.0
    assert canonical["operating_cashflow"] == 17.0
