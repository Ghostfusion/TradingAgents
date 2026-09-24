#!/usr/bin/env python3
"""Field-level fill-rate scorecard across runs (P0 coverage measurement).

Every engine already publishes, per run, which of its declared fields it
measured and which it did not. Nothing reads that **across runs**, so a field
that is never populated is indistinguishable from a field that is populated on
most runs - both look like "some scores are not 100%".

This module answers one question per declared field: **was it measured, and if
not, why not?**

The declared universe comes from ``score_panel.engine_registry()`` - the one
place each engine's own component table (``COMPONENTS`` / ``SUBSCORE_FACTORS``)
is read - so this module never invents a second vocabulary for the same fields.

The classification is the point. A field with a zero fill rate is one of three
things, and only the middle one is a defect in this repo:

* ``unbuilt``    - the declared producer is empty: nobody has written it.
* ``unwired``    - a producer is named and has **no call site** on the live
                   path, so it can never run. This is the ``market_breadth``
                   class: a fully implemented, fully tested producer that no
                   caller ever reaches.
* ``structural`` - a producer is named and IS called, but returns nothing for
                   this instrument (semimonthly short interest, options on an
                   unlisted underlying, a panel this call does not fetch).

Fill rate alone cannot separate those three; the declared producer string plus
a call-site scan can. The call-site scan is AST-based, so a *citation* of a
producer (engines cite their producers as strings in their own component
tables) is not mistaken for a call to it.

Nothing here gates, scores or mutates. It reads ``run_card.json`` and prints.
"""

from __future__ import annotations

import argparse
import ast
import json
import os
import re
import sys
import textwrap

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from scripts.score_panel import engine_registry  # noqa: E402
from tradingagents.strategies.coverage_window import coverage_window  # noqa: E402
from tradingagents.strategies.data_quality import panel_statistic  # noqa: E402

#: Where ``batch.py`` writes its trees. Repo-relative, gitignored.
DEFAULT_REPORTS_DIR = "reports"

#: The tool-evidence entry whose CSV carries the run's own loaded price frame.
PRICE_TOOL = "get_stock_data"

#: The tool-evidence file inside a tree (the run's own record of what it fetched).
EVIDENCE_NAME = "tool_evidence.json"

#: The per-tree card this reads. A tree without one is skipped and counted.
CARD_NAME = "run_card.json"

#: The live path scanned for producer call sites. ``tests`` is deliberately NOT
#: here: a producer referenced only by its own test is exactly the ``unwired``
#: case this module exists to catch. The sibling executor repo is included when
#: it is checked out, because several ``risk_score`` fields are produced there
#: (``pre_market``, ``options_surface``, ``liquidity_risk``) and reporting those
#: as unwired would be a false defect.
LIVE_ROOTS: tuple[str, ...] = ("tradingagents", "scripts", "../TradingExecution")

# --- Declared policy, printed in the output (never a measured coefficient) ---

#: At or above this fill rate a field is healthy.
FILL_OK = 0.95
#: At or above this (and below ``FILL_OK``) a field is intermittent.
FILL_MONITOR = 0.50
#: The float tolerance for "every measured value was zero".
ZERO_EPS = 1e-12

ACTION_OK = "none"
ACTION_MONITOR = "watch for drift"
ACTION_SPARSE = "investigate the sparse runs"
ACTION_UNBUILT = "no producer declared"
ACTION_UNWIRED = "the producer exists and nothing outside its module calls it"
ACTION_STRUCTURAL = "producer is reached; this run supplied no value"
ACTION_UNKNOWN = "cannot tell from the declaration - inspect by hand"


# ---------------------------------------------------------------------------
# Reading the trees
# ---------------------------------------------------------------------------


def load_cards(reports_dir: str, *, limit: int | None = None) -> list[tuple[str, dict]]:
    """``[(tree_name, run_card), ...]`` newest name first, skipping bad cards.

    A malformed or absent card is skipped rather than raising: this is an
    advisory read over a directory the operator points it at.
    """
    root = os.path.abspath(os.path.expanduser(str(reports_dir)))
    if not os.path.isdir(root):
        return []
    out: list[tuple[str, dict]] = []
    for name in sorted(os.listdir(root), reverse=True):
        path = os.path.join(root, name, CARD_NAME)
        if not os.path.isfile(path):
            continue
        try:
            with open(path, encoding="utf-8") as fh:
                card = json.load(fh)
        except (OSError, ValueError):
            continue
        if isinstance(card, dict):
            out.append((name, card))
        if limit is not None and len(out) >= int(limit):
            break
    return out


# ---------------------------------------------------------------------------
# Presence: every signal the run_card states explicitly
# ---------------------------------------------------------------------------
#
# Each engine publishes presence differently, and the difference is real - it is
# not a vocabulary this module may unify:
#
#   technical_score    category ``components``      (list of PRESENT names)
#   risk_score         category ``present``         (list of PRESENT names)
#   fundamental_score  subscore ``coverage.metrics``(list of PRESENT names)
#   regime_score       engine ``components``        (name -> {raw, aligned})
#   sentiment_score    nothing                      -> the complement of absent
#   news_score         nothing                      -> the complement of absent
#
# `declared - absent` is not a second producer for the last two: the engines
# themselves define `absent` as the complement of what they measured
# (`risk_score.score:543`), so reading it back is reading their own rule.


def _iter_categories(block: dict):
    """Every ``{name: category_entry}`` mapping in the block."""
    cats = block.get("categories")
    if isinstance(cats, dict):
        yield cats


def explicit_absent(block: dict) -> set[str]:
    """Every field the card states was NOT measured."""
    out: set[str] = set()
    absent = block.get("absent")
    if isinstance(absent, (list, tuple, set)):
        out.update(str(n) for n in absent)
    for cats in _iter_categories(block):
        for entry in cats.values():
            if not isinstance(entry, dict):
                continue
            if isinstance(entry.get("absent"), (list, tuple, set)):
                out.update(str(n) for n in entry["absent"])
    for sub in (block.get("subscores") or {}).values():
        if isinstance(sub, dict):
            na = sub.get("factors_NA")
            if isinstance(na, (list, tuple, set)):
                out.update(str(n) for n in na)
    comps = block.get("components")
    if isinstance(comps, dict):
        for name, spec in comps.items():
            if isinstance(spec, dict) and spec.get("raw") is None:
                out.add(str(name))
    return out


def explicit_present(block: dict) -> set[str]:
    """Every field the card states WAS measured, plus its measured value.

    A measured ``0.0`` is present - the value is a measurement, not a gap. Only
    an explicit absence or a ``None`` reading counts as missing.
    """
    out: set[str] = set()
    for cats in _iter_categories(block):
        for entry in cats.values():
            if not isinstance(entry, dict):
                continue
            for key in ("components", "present"):
                names = entry.get(key)
                if isinstance(names, (list, tuple, set, dict)):
                    out.update(str(n) for n in names)
    for sub in (block.get("subscores") or {}).values():
        if isinstance(sub, dict):
            cov = sub.get("coverage")
            if isinstance(cov, dict) and isinstance(cov.get("metrics"), (list, tuple, set)):
                out.update(str(n) for n in cov["metrics"])
    comps = block.get("components")
    if isinstance(comps, dict):
        for name, spec in comps.items():
            if isinstance(spec, dict):
                if spec.get("raw") is not None:
                    out.add(str(name))
            elif spec is not None and not isinstance(spec, dict):
                out.add(str(name))
    return out


def measured_values(block: dict) -> dict[str, float]:
    """``{field: value}`` where the card carries the number, not just the name."""
    out: dict[str, float] = {}
    comps = block.get("components")
    if isinstance(comps, dict):
        for name, spec in comps.items():
            val = spec.get("aligned") if isinstance(spec, dict) else spec
            if isinstance(val, (int, float)) and not isinstance(val, bool):
                out[str(name)] = float(val)
    return out


def field_states(block: dict, declared: dict) -> dict[str, str]:
    """``{field: "present" | "absent"}`` for the fields this card states.

    Fields the card says nothing about are OMITTED - they leave the denominator
    rather than being guessed at (the same rule ``breadth_with_gate`` applies to
    a panel below ``min_n``).
    """
    if not isinstance(block, dict):
        return {}
    absent = explicit_absent(block)
    present = explicit_present(block)
    has_absent_list = isinstance(block.get("absent"), (list, tuple, set))
    if not present and has_absent_list:
        # The complement rule, stated by the engines themselves. An EMPTY
        # `absent` list is the strongest form of it - nothing is missing, so
        # every declared field was measured.
        present = {f for f in declared if f not in absent}
    states: dict[str, str] = {}
    for f in present:
        states[f] = "present"
    for f in absent:
        states.setdefault(f, "absent")
    return states


# ---------------------------------------------------------------------------
# The call-site scan: is the declared producer ever reached?
# ---------------------------------------------------------------------------


def _module_file(module: str) -> str | None:
    """Resolve a dotted module tail (``news_relevance``) to a repo-relative file."""
    tail = module.rsplit(".", 1)[-1]
    if not tail:
        return None
    for root in LIVE_ROOTS:
        if not os.path.isdir(root):
            continue
        for dirpath, _dirs, files in os.walk(root):
            if f"{tail}.py" in files:
                return os.path.join(dirpath, f"{tail}.py").replace("\\", "/")
    return None


def parse_producer(spec: str) -> tuple[str | None, tuple[str, ...]]:
    """``(own_file_or_None, (func, ...))`` from a declared producer string.

    Handles both declared shapes and the ``a + b`` two-producer form. Returns
    ``(None, ())`` when the string names no callable (a prose note, an empty
    producer, ``caller-supplied``).
    """
    text = str(spec or "").strip()
    if not text:
        return None, ()
    text = text.split("(")[0].strip()
    own: str | None = None
    funcs: list[str] = []
    for part in text.split("+"):
        part = part.strip()
        if not part:
            continue
        if "::" in part:
            head, rest = part.split("::", 1)
            head = head.strip()
            own = own or (head if head.endswith(".py") else _module_file(head))
        elif "." in part:
            head, rest = part.rsplit(".", 1)
            own = own or _module_file(head)
        else:
            # A bare ``name:line`` - the second half of a two-producer string
            # such as ``sentiment.mention_volume:43 + decayed_weight:91``. It
            # names a callable with no module of its own. Requiring the ``:line``
            # keeps a prose note ("caller-supplied", "no producer declared") from
            # being read as a function name.
            if not re.fullmatch(r"[A-Za-z_]\w*:\d+", part):
                continue
            rest = part
        m = re.match(r"\s*([A-Za-z_]\w*)", rest.split(":")[0])
        if m:
            funcs.append(m.group(1))
    return own, tuple(funcs)


def _called_names(path: str) -> set[str]:
    """Every function name called in one file, read from its AST.

    AST, not a text search: the engines cite their producers as string literals
    in their own component tables, and a citation is not a call.

    Import aliases are resolved, because the live path routinely renames a
    producer on import - ``from ...liquidity_risk import days_to_absorb as
    _dta`` then ``_dta(...)`` (``analysis_tools.get_liquidation_days``). Reading
    only the call node's own name would report that producer as never called,
    which is a manufactured defect.
    """
    try:
        with open(path, encoding="utf-8") as fh:
            tree = ast.parse(fh.read(), filename=path)
    except (OSError, SyntaxError, ValueError):
        return set()
    aliases: dict[str, str] = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            for a in node.names:
                aliases[a.asname or a.name] = a.name
        elif isinstance(node, ast.Import):
            for a in node.names:
                local = a.asname or a.name.split(".")[0]
                aliases[local] = a.name.rsplit(".", 1)[-1]
    names: set[str] = set()
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        fn = node.func
        called: str | None = None
        if isinstance(fn, ast.Name):
            called = fn.id
        elif isinstance(fn, ast.Attribute):
            called = fn.attr
        if called:
            names.add(called)
            if called in aliases:
                names.add(aliases[called])
    return names


def _repo_relative(path: str) -> str:
    return os.path.abspath(path).replace("\\", "/")


def _defines(path: str, funcs: tuple[str, ...]) -> bool:
    """Does this file define any of these top-level function names?"""
    try:
        with open(path, encoding="utf-8") as fh:
            tree = ast.parse(fh.read(), filename=path)
    except (OSError, SyntaxError, ValueError):
        return False
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name in funcs:
            return True
    return False


def _resolve_own(own: str | None) -> str | None:
    """Resolve a producer's own file, which may be package-relative.

    The engines spell their producers the house way - ``strategies/
    market_breadth.py``, not ``tradingagents/strategies/market_breadth.py`` - so
    a bare relative path is tried as-is and then under each live root. This is
    the same two-candidate resolution ``test_regime_score`` applies to the same
    strings.
    """
    if not own:
        return None
    if os.path.isfile(own):
        return own
    for root in LIVE_ROOTS:
        cand = os.path.join(root, own)
        if os.path.isfile(cand):
            return cand
    return None


def has_call_site(producer: str, *, roots: tuple[str, ...] = LIVE_ROOTS) -> bool | None:
    """Is the declared producer called anywhere outside its own module?

    ``None`` - never a silent ``False`` - when the producer string cannot be
    tied to a function this layer can see. Three cases return ``None``: no
    callable is named at all; the named module resolves to no file here; or the
    resolved file does not actually define the named function (a same-named
    module in another checkout, e.g. ``book_risk``). Claiming ``unwired`` on any
    of those would manufacture a defect that does not exist.
    """
    own, funcs = parse_producer(producer)
    if not funcs:
        return None
    resolved = _resolve_own(own)
    if resolved is None:
        return None
    own_abs = _repo_relative(resolved)
    if not _defines(resolved, funcs):
        return None
    for root in roots:
        if not os.path.isdir(root):
            continue
        for dirpath, _dirs, files in os.walk(root):
            for fname in files:
                if not fname.endswith(".py"):
                    continue
                path = os.path.join(dirpath, fname)
                if _repo_relative(path) == own_abs:
                    continue
                if _called_names(path) & set(funcs):
                    return True
    return False


# ---------------------------------------------------------------------------
# Classification
# ---------------------------------------------------------------------------


def classify(fill: float | None, producer: str, wired: bool | None,
             *, has_producer_column: bool = True) -> str:
    """The field's class, from its fill rate and whether its producer is reached.

    A healthy field is ``ok`` regardless of its producer string. A field that is
    never measured is only actionable once we know whether the producer exists
    and whether anything calls it.

    ``has_producer_column`` is False for an engine whose declaration carries no
    producer at all (``fundamental_score``, whose factors come from
    ``factor_schema.SUBSCORE_FACTORS``). An empty producer there says nothing
    about the field, so it is ``unknown`` rather than a manufactured ``unbuilt``.
    """
    if fill is None:
        return "unknown"
    if fill >= FILL_OK:
        return "ok"
    if fill >= FILL_MONITOR:
        return "monitor"
    if fill > 0.0:
        return "sparse"
    if not str(producer or "").strip():
        return "unbuilt" if has_producer_column else "unknown"
    if wired is True:
        return "structural"
    if wired is False:
        return "unwired"
    return "unknown"


def action_for(klass: str) -> str:
    """The one-line action for a class, so the report is a to-do list."""
    return {
        "ok": ACTION_OK,
        "monitor": ACTION_MONITOR,
        "sparse": ACTION_SPARSE,
        "unbuilt": ACTION_UNBUILT,
        "unwired": ACTION_UNWIRED,
        "structural": ACTION_STRUCTURAL,
        "unknown": ACTION_UNKNOWN,
    }.get(klass, ACTION_UNKNOWN)


#: Why a field CANNOT be filled, keyed ``"engine.field"``.
#:
#: This exists so an empty field is STATED rather than left as a blank someone
#: later fills with a number the repo cannot support. Every entry cites the
#: definition site it rests on, and the entries marked "do not build" are
#: refusals, not a backlog.
GAP_REASONS: dict[str, str] = {
    "risk_score.gap_atr": (
        "WIRED: pre_market.premarket_gap over the run's own last two bars. Trees "
        "written before the fix still read absent - the fill rates come from disk, "
        "the wiring from live code"
    ),
    "risk_score.implied_move_pct": (
        "WIRED: options_surface.implied_move_pct over the chain the gamma and "
        "derivatives-flow leaves already read, converted percent->fraction at the "
        "seam. Trees written before the fix still read absent"
    ),
    "risk_score.iv_percentile": (
        "needs a per-day IV HISTORY no producer can supply, and the code says so "
        "(analysis_tools.get_options_iv_read prints 'IV percentile: n/a'; "
        "tests/test_calc_agent_wiring.py records it). Filling it means inventing "
        "the history - leave it absent"
    ),
    "risk_score.sector_max_share": (
        "the declared producer returns the WRONG SHAPE: "
        "portfolio_optimizer.enforce_sector_exposure:169 returns the adjusted "
        "WEIGHT DICT (:196), not the scalar this component ramps (0.15, 0.45). A "
        "scalar needs a shared sector_weights() over that same aggregation, and "
        "the book exists only when risk_basket_tickers/holdings_tickers are "
        "configured (book_context.configured_basket:44); no ticker->sector map "
        "producer exists either, only per-name network "
        "yfinance_sector.fetch_sector:64"
    ),
    "risk_score.through_stop": (
        "needs the PRIOR plan's stop/entry, reachable only through "
        "pre_market.load_prior_state:332 / parse_planned_levels:413, which nothing "
        "under tradingagents/ calls (only scripts/pre_market_review.py). "
        "premarket_gap answers through_stop=False when handed no stop, so reading "
        "it here would FABRICATE 'did not trade through the stop' - do not wire it"
    ),
    "sentiment_score.mention_heat": (
        "WIRED: sentiment.mention_volume over the per-day count series "
        "daily_sentiment_sma already carries. Trees written before the fix still "
        "read absent"
    ),
    "sentiment_score.short_pct_float": (
        "the declared producer returns the WRONG TYPE: "
        "yfinance_short_interest.get_short_interest_yfinance:37 returns a MARKDOWN "
        "STRING (:95). shortPercentOfFloat is read at :55 and rendered x100 at :77, "
        "so a numeric sibling is needed. The producer is NOT dead code - it is "
        "dispatched through interface.VENDOR_METHODS['get_short_interest'] (:591) "
        "and runs in every market-analyst gather, which an AST call scan cannot see"
    ),
    "news_score.persistence": (
        "WIRED: sentiment.mention_volume over the same per-day count series. The "
        "declaration's second citation (sentiment.decayed_weight:91) has NO call "
        "site - mention_volume accepts no weights, so a decayed baseline would be a "
        "second producer of one ratio. Trees written before the fix still read "
        "absent"
    ),
    "news_score.fundamental_impact": (
        "no revenue or margin ESTIMATE exists anywhere in the repo - only EPS "
        "estimate levels, themselves gated behind analyst_revisions. Building it "
        "means inventing the input: do not build it"
    ),
    "news_score.regulatory_legal": (
        "the only cheap proxy is a litigious-word share (text_factors.lm_tone:147) "
        "and the engine ALREADY REJECTED it - event_state.FAMILY_AVAILABILITY "
        "records the court/legal family as ABSENT with evidence "
        "(event_state.py:109-125). An honest measure needs a new source"
    ),
    "news_score.industry_shock": (
        "BUILDABLE from data the run already fetches: the 11 SPDR series come from "
        "get_sector_rank (analysis_tools.py:3544-3548) plus one fetch_sector "
        "(:3558). Not yet wired"
    ),
    "news_score.guidance_change": (
        "BUILDABLE with no new vendor: benzinga.get_guidance_benzinga:456 already "
        "parses numeric min/max/prior (:490-503) and then discards them into prose "
        "(:519). Needs a numeric producer; the vendor is default-off"
    ),
}

#: Class defaults - the weakest reason, stating only what the scan can prove.
_GAP_DEFAULTS: dict[str, str] = {
    "unbuilt": "no producer is declared for this field",
    "unwired": (
        "the declared producer has no DIRECT call site. An indirect dispatch (a "
        "VENDOR_METHODS / route_to_vendor dict lookup) reads exactly the same way, "
        "so verify before calling it dead"
    ),
    "structural": (
        "the declared producer is reached, yet no tree measured this field - check "
        "whether the producer can emit the DECLARED quantity (units, return type, "
        "sign)"
    ),
    "unknown": (
        "the producer string names no callable this layer can resolve, so neither "
        "wired nor dead can be claimed"
    ),
}


def _absent_reasons(module: str) -> dict[str, str]:
    """The engine's OWN absent-reason table, when it declares one.

    ``news_score.ABSENT_REASONS`` is the engine itself stating why a component
    has no producer. Reading it here means this report's "why" cannot drift from
    the engine's, and an engine that adds a reason gets it printed for free.
    """
    if not module:
        return {}
    try:
        import importlib

        table = getattr(importlib.import_module(module), "ABSENT_REASONS", None)
    except Exception:  # noqa: BLE001 - a missing table is not a finding
        return {}
    if not isinstance(table, dict):
        return {}
    return {str(k): str(v) for k, v in table.items()}


def gap_reason(engine: str, field: str, klass: str, *, absent: dict[str, str]) -> str | None:
    """Why this field cannot be filled, or ``None`` when it IS measured.

    Order: this module's authored reason (which cites a definition site), then
    the ENGINE's own reason (so the two cannot drift), then a class default that
    says only what the scan can prove.
    """
    if klass in ("ok", "monitor", "sparse"):
        return None
    authored = GAP_REASONS.get(f"{engine}.{field}")
    if authored:
        return authored
    declared = absent.get(field)
    if declared:
        return f"{declared} (the engine's own reason)"
    return _GAP_DEFAULTS.get(klass, _GAP_DEFAULTS["unknown"])


# ---------------------------------------------------------------------------
# The coverage window, per symbol
# ---------------------------------------------------------------------------
#
# A tree is one run of one symbol, and its own tool evidence holds the price
# frame that run loaded (``get_stock_data``). Reading that frame back is reading
# the run's own input - no new vendor call - so the coverage window costs
# nothing here. The requested date range is the calendar the frame was aligned
# to; positions before the symbol's first observed bar are the padding H10
# measures. The dependent panel statistic is read through ``data_quality``, so a
# padded window reports ``unavailable`` rather than a number.


def _load_evidence(tree_dir: str) -> dict | None:
    """The tree's own ``tool_evidence.json``, or ``None`` when absent/bad."""
    path = os.path.join(tree_dir, EVIDENCE_NAME)
    try:
        with open(path, encoding="utf-8") as fh:
            data = json.load(fh)
    except (OSError, ValueError):
        return None
    return data if isinstance(data, dict) else None


def _parse_price_content(content: str) -> list[tuple[str, float]]:
    """``(date, close)`` rows from a ``get_stock_data`` markdown/CSV payload."""
    rows: list[tuple[str, float]] = []
    for line in str(content or "").splitlines():
        parts = line.split(",")
        if len(parts) < 5:
            continue
        date = parts[0].strip()
        if not re.match(r"^\d{4}-\d{2}-\d{2}$", date):
            continue
        try:
            close = float(parts[4])
        except ValueError:
            continue
        rows.append((date, close))
    return rows


def _price_entry(evidence: dict, ticker: str) -> tuple[list[tuple[str, float]], str, str]:
    """``(rows, start_date, end_date)`` for the run's own loaded price frame."""
    entries = (evidence or {}).get("market")
    if not isinstance(entries, list):
        return [], "", ""
    fallback: tuple[list[tuple[str, float]], str, str] | None = None
    for entry in entries:
        if not isinstance(entry, dict) or entry.get("tool") != PRICE_TOOL:
            continue
        rows = _parse_price_content(entry.get("content"))
        if not rows:
            continue
        args = entry.get("args")
        if isinstance(args, str):
            try:
                args = ast.literal_eval(args)
            except (ValueError, SyntaxError):
                args = {}
        args = args if isinstance(args, dict) else {}
        got = (rows, str(args.get("start_date") or ""), str(args.get("end_date") or ""))
        if ticker and str(args.get("symbol") or "") == ticker:
            return got
        if fallback is None:
            fallback = got
    return fallback or ([], "", "")


def _calendar_panel(rows: list[tuple[str, float]], start: str, end: str):
    """The requested calendar with the observed closes, missing where no bar.

    Positions before the symbol's first observed bar are NaN - exactly the
    padding a heterogeneous listing history creates - so ``coverage_window``
    counts them. Interior holidays also read as missing, which ``n_bars`` (the
    valid count) already accounts for; only the leading run is padding.
    """
    import pandas as pd

    observed = {date: close for date, close in rows if date}
    dates = sorted(observed)
    if not dates:
        return None
    lo = start if start and start <= dates[0] else dates[0]
    hi = end if end and end >= dates[-1] else dates[-1]
    try:
        calendar = [d.strftime("%Y-%m-%d") for d in pd.bdate_range(lo, hi)]
    except Exception:  # noqa: BLE001 - a bad range falls back to the observed bars
        calendar = dates
    if not calendar or calendar[0] > dates[0]:
        calendar = dates
    return pd.Series([observed.get(d) for d in calendar],
                     index=pd.to_datetime(calendar))


def _coverage_gate() -> bool:
    """Is the H10 per-symbol coverage window switched on? (``enable_coverage_window``)

    Off by default, so a gate-off scorecard prints exactly the sections it
    printed before the per-symbol window existed. A config read must never
    break the report it guards.
    """
    try:
        from tradingagents.dataflows.config import get_config

        cfg = get_config() or {}
    except Exception:  # noqa: BLE001 - a config read must never break the read
        cfg = {}
    return bool(cfg.get("enable_coverage_window", False))


def symbol_coverage(tree: str, card: dict, evidence: dict | None) -> dict:
    """The coverage-window line for one symbol (one run tree).

    Reads the tree's own loaded frame and reports its window; a tree with no
    frame degrades to ``unavailable`` with the reason, never to a zero. The
    dependent statistic is ``data_quality.panel_statistic`` so a padded window
    is refused (H10).
    """
    ticker = str(card.get("ticker") or "")
    rows, start, end = _price_entry(evidence or {}, ticker)
    panel = _calendar_panel(rows, start, end) if rows else None
    window = coverage_window(panel)
    stat = panel_statistic(panel)
    return {
        "tree": tree,
        "ticker": ticker,
        "window": window,
        "statistic": stat["statistic"],
        "unavailable": stat["unavailable"],
    }


def _label(value) -> str:
    """A window label as a date string when it can be one, else ``str``."""
    fmt = getattr(value, "strftime", None)
    return fmt("%Y-%m-%d") if fmt else str(value)


# ---------------------------------------------------------------------------
# The scorecard
# ---------------------------------------------------------------------------


def build_scorecard(reports_dir: str = DEFAULT_REPORTS_DIR, *, limit: int | None = None,
                    engines: tuple[str, ...] | None = None) -> dict:
    """Per-field fill rates over every tree under ``reports_dir``.

    The denominator for a field is the number of trees where its engine was
    **measured** - an engine whose gate was off is not part of the scorecard, so
    it cannot drag a field's fill rate down (master rule 3).
    """
    registry = engine_registry()
    cards = load_cards(reports_dir, limit=limit)
    wanted = tuple(engines) if engines else tuple(
        name for name, ent in registry.items() if ent.get("available")
    )

    engines_out: dict[str, dict] = {}
    for engine in wanted:
        ent = registry.get(engine) or {}
        declared = {str(k): (v or {}) for k, v in (ent.get("factors") or {}).items()}
        if not declared:
            continue
        counts: dict[str, int] = dict.fromkeys(declared, 0)
        zeros: dict[str, int] = dict.fromkeys(declared, 0)
        stated: dict[str, int] = dict.fromkeys(declared, 0)
        trees_measured = 0
        for _name, card in cards:
            block = card.get(engine)
            if not isinstance(block, dict) or block.get("score") is None:
                # The engine was not part of this tree's scorecard.
                continue
            trees_measured += 1
            states = field_states(block, declared)
            values = measured_values(block)
            for field, state in states.items():
                if field not in counts:
                    continue
                stated[field] += 1
                if state == "present":
                    counts[field] += 1
                    if abs(values.get(field, 1.0)) <= ZERO_EPS and field in values:
                        zeros[field] += 1
        fields: dict[str, dict] = {}
        producer_column = any(
            str((spec or {}).get("producer") or "").strip() for spec in declared.values()
        )
        absent_reasons = _absent_reasons(str(ent.get("module") or ""))
        for field, spec in declared.items():
            denom = stated[field]
            fill = (counts[field] / denom) if denom else None
            producer = str((spec or {}).get("producer") or "")
            wired = has_call_site(producer) if (fill == 0.0) else None
            klass = classify(fill, producer, wired, has_producer_column=producer_column)
            fields[field] = {
                "category": str((spec or {}).get("category") or ""),
                "producer": producer,
                "measured": counts[field],
                "stated": denom,
                "fill_rate": fill,
                "wired": wired,
                "class": klass,
                "action": action_for(klass),
                "gap": gap_reason(engine, field, klass, absent=absent_reasons),
                "flat_zero": (zeros[field] if zeros[field] else 0),
            }
        engines_out[engine] = {
            "module": ent.get("module", ""),
            "trees_measured": trees_measured,
            "declared": len(declared),
            "fields": fields,
        }

    symbols = [] if not _coverage_gate() else [
        symbol_coverage(name, card, _load_evidence(os.path.join(reports_dir, name)))
        for name, card in cards
    ]
    return {
        "reports_dir": os.path.abspath(os.path.expanduser(str(reports_dir))),
        "trees": len(cards),
        "trees_with_cards": len(cards),
        "engines": engines_out,
        "symbols": symbols,
    }


# ---------------------------------------------------------------------------
# Rendering
# ---------------------------------------------------------------------------


def _tally(fields: dict) -> dict[str, int]:
    out: dict[str, int] = {}
    for f in fields.values():
        out[f["class"]] = out.get(f["class"], 0) + 1
    return out


def render_text(report: dict) -> str:
    """The human-readable scorecard: per engine, worst fields first."""
    engines = report.get("engines") or {}
    lines = [
        "## Field coverage scorecard (advisory)",
        f"trees read: {report.get('trees', 0)} | "
        f"engines measured: {len(engines)} | "
        f"thresholds: ok >= {FILL_OK}, monitor >= {FILL_MONITOR}",
    ]
    if not engines or not report.get("trees"):
        lines.append("no trees with a run_card.json under the reports dir")
        return "\n".join(lines)

    total = {"ok": 0, "monitor": 0, "sparse": 0, "unbuilt": 0,
             "unwired": 0, "structural": 0, "unknown": 0}
    for engine in sorted(engines):
        ent = engines[engine]
        tally = _tally(ent["fields"])
        for k, v in tally.items():
            total[k] = total.get(k, 0) + v
        lines.append("")
        lines.append(f"### {engine}  (module {ent['module']}; "
                     f"trees measured {ent['trees_measured']}; "
                     f"declared {ent['declared']})")
        lines.append(f"  {tally}")
        rows = sorted(
            ent["fields"].items(),
            key=lambda kv: (kv[1]["fill_rate"] if kv[1]["fill_rate"] is not None else 1.0,
                            kv[0]),
        )
        for field, f in rows:
            fill = f["fill_rate"]
            shown = "  n/a" if fill is None else f"{fill * 100:5.1f}%"
            mark = {"ok": "  ", "monitor": "! ", "sparse": "! ",
                    "unbuilt": "X ", "unwired": "X ", "structural": "x "}.get(f["class"], "? ")
            lines.append(
                f"  {mark}{shown} {field:<28} {f['measured']:>3}/{f['stated']:<3} "
                f"{f['class']:<11} {f['action']}"
            )
            if f["producer"]:
                lines.append(f"       producer: {f['producer']}")
            if f.get("gap"):
                # The point of the report: an empty field carries its REASON, so
                # the gap is visible instead of inviting a fabricated number.
                lines.append(textwrap.fill(
                    str(f["gap"]), width=96,
                    initial_indent="       why: ", subsequent_indent="            ",
                ))
            if f["flat_zero"]:
                lines.append(f"       flat_zero: measured {f['flat_zero']} time(s), "
                             f"always 0.0 - check for a placeholder")

    lines.append("")
    symbols = report.get("symbols") or []
    if symbols:
        lines.append("### symbols (coverage window, read off the tree's own loaded frame)")
        for s in symbols:
            w = s.get("window") or {}
            name = s.get("ticker") or s.get("tree") or "?"
            if w.get("first_valid") is None:
                lines.append(f"  {name:<12} n/a  {s.get('unavailable') or 'no window'}")
                continue
            lines.append(
                f"  {name:<12} {_label(w['first_valid'])}..{_label(w['last_valid'])}  "
                f"n_bars={w['n_bars']}  padded_days={w['padded_days']}  "
                f"{w['alignment']}"
            )
        lines.append("")
    lines.append(f"totals: {total}")
    lines.append("legend: X = actionable gap (unbuilt/unwired), "
                 "x = structural (producer runs, data absent), ! = partial")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=(__doc__ or "").splitlines()[0])
    parser.add_argument("--reports-dir", default=DEFAULT_REPORTS_DIR,
                        help="dir holding the run trees (default: reports)")
    parser.add_argument("--limit", type=int, default=None,
                        help="read at most N trees, newest first")
    parser.add_argument("--engine", action="append", default=None,
                        help="restrict to an engine (repeatable)")
    parser.add_argument("--json", action="store_true", help="emit JSON, not text")
    parser.add_argument("--actionable", action="store_true",
                        help="print only the unbuilt/unwired fields")
    args = parser.parse_args(argv)

    report = build_scorecard(args.reports_dir, limit=args.limit,
                             engines=tuple(args.engine) if args.engine else None)
    if args.json:
        print(json.dumps(report, indent=2, sort_keys=True))
        return 0
    if args.actionable:
        for engine in sorted(report.get("engines") or {}):
            for field, f in sorted((report["engines"][engine]["fields"]).items()):
                if f["class"] in ("unbuilt", "unwired"):
                    print(f"{engine:<20} {field:<28} {f['class']:<9} "
                          f"{f['producer'] or '(no producer declared)'}")
                    if f.get("gap"):
                        print(textwrap.fill(
                            str(f["gap"]), width=96,
                            initial_indent="    why: ", subsequent_indent="         ",
                        ))
        return 0
    print(render_text(report))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


__all__ = [
    "ACTION_MONITOR",
    "ACTION_OK",
    "ACTION_SPARSE",
    "ACTION_STRUCTURAL",
    "ACTION_UNBUILT",
    "ACTION_UNKNOWN",
    "ACTION_UNWIRED",
    "DEFAULT_REPORTS_DIR",
    "FILL_MONITOR",
    "FILL_OK",
    "GAP_REASONS",
    "LIVE_ROOTS",
    "PRICE_TOOL",
    "action_for",
    "build_scorecard",
    "classify",
    "explicit_absent",
    "explicit_present",
    "field_states",
    "gap_reason",
    "has_call_site",
    "load_cards",
    "main",
    "measured_values",
    "parse_producer",
    "render_text",
    "symbol_coverage",
]
