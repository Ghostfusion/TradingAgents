#!/usr/bin/env python3
"""WP-10 - the validation panel and the factor-measurement layer.

Implements `docs/scores/IMPLEMENTATION_PLAN.md` section 7 (WP-10) and its exit
criteria in section 9, Phase C, plus `docs/scores/README.md` Q4 (the full EODHD
US panel is the validation universe).

Three objects, and they are separate on purpose:

1. **The panel** - one cross-sectional snapshot per trading date,
   ``data_cache_dir/panels/<date>.json``, of ``{ticker: {metric: value}}``.
   The vendor's bulk-fundamentals endpoint is the fundamentals leg
   (500-symbol chunks; 100 API calls a whole-exchange request, ``100 + N`` when
   a ``symbols`` list is passed - plan section 3.2/section 15); the technical
   leg assembles the ``TechnicalScore`` components from each name's own bars up
   to that date. **Per-date caching is the contract**: a date whose file exists
   is never re-fetched, so a second invocation makes zero network calls.
   Every file records its call cost, fetch timestamp and coverage under the one
   reserved ``_meta`` key (a ticker can never be named ``_meta``).

2. **The statistics** - per factor and per sub-score, from the harness that
   already exists, `alpha_health.score_evaluation_rows`: IC / rank IC / ICIR,
   the decile means with their ``spread`` (D10 - D1) and ``ordering``
   (correctly ordered adjacent decile pairs / 9), coverage, stability
   (= persistence) and turnover - plus, here, the out-of-sample split and the
   multiple-testing machinery that was already in the repo and unused on
   fundamentals (`evaluate.purged_cpcv_splits`, `deflated_sharpe`, `pbo_flag`,
   `reality_check`, `spa`).

3. **The redundancy matrix** - pairwise Spearman/Pearson across the measured
   factors, with the two blocks the plan names reported explicitly: the 50%
   trend + momentum + relative-strength block in ``TechnicalScore`` and the
   FCF-yield cluster in ``FundamentalScore``. The matrix is the documented gate
   on any weight table, not a decoration.

**The label.** A panel below the cross-section floors (owner Q4: hundreds of
eligible names, plan section 9 Phase C) is ``INSUFFICIENT_CROSS_SECTION`` and
this layer produces **no weight vector** - the key is ``None`` with the reason,
never a vector the reader might mistake for a measurement. The floors live in
one place (`alpha_health.cross_section_status`), not here.

**What this module never does.** It is not on a report path, it reads no gate
(`enable_score_eval_rows` gates the *harness* in the report path; this script is
manual and only echoes that gate's state), it imports no sizing path, no
``risk_governor``, no ``GATE_PRECEDENCE`` and no ``decision_guardrail``, and it
invents no coefficient: the only weight vectors it prints are the engines' own
declared tables, labelled with their measured evidence and ``RESEARCH_ONLY``.

**What cannot be verified here.** The EODHD *Extended Fundamentals* plan is
support-gated on the vendor side, so the live bulk fetch has no credentials to
be exercised against: the transport is injectable, and the caching / chunking /
cost / labelling are proven against a stub (``tests/test_score_panel.py``). The
payload field paths in ``BULK_YEARLY_STATEMENTS`` are declared, documented as
unverified, and corrected in one place when the vendor grants the plan.

Examples::

    py -3.12 scripts/score_panel.py --dates 2026-09-17 --symbols-file sp500.txt
    py -3.12 scripts/score_panel.py --dates-file trading_dates.txt --evaluate-only
    py -3.12 scripts/score_panel.py --symbols-file sp500.txt --cost-only
"""

from __future__ import annotations

import argparse
import json
import math
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import NamedTuple

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from tradingagents.strategies import alpha_health, evaluate  # noqa: E402

# --- The vendor's own cost model (plan section 3.2, section 15) --------------

#: The bulk endpoint's per-request cap (plan section 15: "500 symbols max").
CHUNK_SIZE = 500
#: One whole-exchange bulk request costs this many API calls.
BULK_REQUEST_CALLS = 100
#: A `symbols` list request costs `BULK_REQUEST_CALLS + len(chunk)`.
PER_SYMBOL_CALLS = 1
#: The bulk endpoint's exchange codes; the generic `US` code is for the symbol
#: list, and the plan records that the snapshot variant 404s on it.
EXCHANGE_CODES = ("NASDAQ", "NYSE", "AMEX", "BATS")

#: The one reserved key in a panel file. A ticker symbol cannot be named this.
META_KEY = "_meta"
PANELS_DIRNAME = "panels"

#: The harness gate. Read-only here: this script is manual, and it never
#: invents a second measurement switch (plan section 7, Gate).
HARNESS_GATE = "enable_score_eval_rows"

# --- Declared policy, printed in the output (never a measured coefficient) ---

#: |Spearman| at or above which two factors are treated as one bet.
REDUNDANT_ABS_CORR = 0.80
#: Below this many common observations a pairwise correlation is withheld.
MIN_PAIRS = 10
#: The out-of-sample band (leading train / trailing OOS).
OOS_TRAIN_FRAC = 0.7
#: Below this spread dispersion the deflated Sharpe divides by float noise.
DSR_MIN_DISPERSION = 1e-12

# --- The status vocabulary (master section 1.4 / plan section 6) -------------
#
# `ADVISORY` is a deterministic diagnostic: the harness rows and the redundancy
# matrix are computed from the panel and state their own `n`, so they are
# advisory measurements. `RESEARCH_ONLY` is an **unvalidated combination**: the
# weight vectors this layer prints are the engines' declared tables beside their
# measured evidence, never a promoted vector (the ladder to `VALIDATED` is
# WP-11's, and it is never automatic).
STATUS_ADVISORY = "ADVISORY"
STATUS_RESEARCH_ONLY = "RESEARCH_ONLY"


# ---------------------------------------------------------------------------
# Panel files, chunking and cost
# ---------------------------------------------------------------------------


def default_cache_dir() -> str:
    """The configured ``data_cache_dir`` (never raises)."""
    try:
        from tradingagents.default_config import DEFAULT_CONFIG

        return str(
            DEFAULT_CONFIG.get("data_cache_dir")
            or os.path.expanduser("~/.tradingagents")
        )
    except Exception:  # noqa: BLE001 - a config read must not break the panel
        return os.path.expanduser("~/.tradingagents")


def panel_path(cache_dir: str, date: str) -> str:
    """``<cache_dir>/panels/<date>.json`` - one file per trading date."""
    return os.path.join(os.path.abspath(os.path.expanduser(str(cache_dir))),
                        PANELS_DIRNAME, f"{date}.json")


def split_chunks(symbols, size: int = CHUNK_SIZE) -> list[list[str]]:
    """Uppercase, de-duplicate and chunk a symbol list (order preserved).

    The chunk size is the vendor's own cap: a request carrying more than
    ``CHUNK_SIZE`` symbols is not a request the bulk endpoint accepts.
    """
    size = max(1, int(size))
    codes: list[str] = []
    seen: set[str] = set()
    for s in symbols or []:
        code = str(s or "").strip().upper()
        if code and code not in seen:
            seen.add(code)
            codes.append(code)
    return [codes[i:i + size] for i in range(0, len(codes), size)]


def estimate_cost(n_symbols: int, *, chunk_size: int = CHUNK_SIZE) -> dict:
    """The API-call cost of a ``symbols``-list build, from the vendor's model.

    ``100 + N`` per request with a 500-symbol cap, so N symbols in c chunks
    cost ``100 * c + N``. A whole-exchange request is a flat 100 calls
    (``exchange_cost``), which is why the cost is printed *before* a run.
    """
    n = max(0, int(n_symbols))
    chunks = math.ceil(n / max(1, int(chunk_size))) if n else 0
    return {
        "source": "bulk fundamentals (EODHD Extended Fundamentals)",
        "symbols": n,
        "chunk_size": int(chunk_size),
        "chunks": chunks,
        "api_calls": BULK_REQUEST_CALLS * chunks + PER_SYMBOL_CALLS * n,
        "model": (
            f"{BULK_REQUEST_CALLS} calls per request + {PER_SYMBOL_CALLS} per "
            f"symbol, {int(chunk_size)}-symbol cap per request "
            "(docs/scores/IMPLEMENTATION_PLAN.md section 3.2)"
        ),
    }


def exchange_cost(n_requests: int) -> int:
    """Cost of whole-exchange requests: a flat ``BULK_REQUEST_CALLS`` each."""
    return BULK_REQUEST_CALLS * max(0, int(n_requests))


def read_panel(path: str) -> tuple[dict, dict] | None:
    """``(rows, meta)`` for a cached date, or None when the file is absent/bad.

    A file that cannot be parsed is treated as absent (it is re-fetched), never
    as an empty panel - a corrupt cache must not silently become a thin panel.
    """
    if not path or not os.path.exists(path):
        return None
    try:
        with open(path, encoding="utf-8") as fh:
            raw = json.load(fh)
    except (OSError, ValueError):
        return None
    if not isinstance(raw, dict):
        return None
    meta = raw.get(META_KEY) or {}
    rows = {k: v for k, v in raw.items() if k != META_KEY and isinstance(v, dict)}
    return rows, meta


def write_panel(path: str, rows: dict, meta: dict) -> None:
    """Write one date's panel: the rows plus the reserved ``_meta`` record."""
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    payload = {META_KEY: meta}
    for ticker in sorted(rows or {}):
        payload[str(ticker).upper()] = rows[ticker]
    tmp = f"{path}.tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(payload, fh, indent=0, sort_keys=True, default=str)
    os.replace(tmp, path)


# ---------------------------------------------------------------------------
# The vendor leg: bulk fundamentals -> canonical financials -> panel row
# ---------------------------------------------------------------------------
#
# UNVERIFIED FIELD PATHS (the one thing this environment cannot check): the
# Extended Fundamentals plan is support-gated, so no live bulk payload could be
# read while writing this. The map below is therefore declared policy, kept in
# ONE table so a live run corrects it once, and the panel records the metrics it
# could not derive rather than substituting a number.

#: canonical item -> (EODHD statement block, field name)
BULK_YEARLY_STATEMENTS: dict[str, tuple[str, str]] = {
    "revenue": ("Income_Statement", "totalRevenue"),
    "net_income": ("Income_Statement", "netIncome"),
    "operating_income": ("Income_Statement", "operatingIncome"),
    "gross_profit": ("Income_Statement", "grossProfit"),
    "eps": ("Income_Statement", "eps"),
    "total_assets": ("Balance_Sheet", "totalAssets"),
    "total_liabilities": ("Balance_Sheet", "totalLiabilities"),
    "total_equity": ("Balance_Sheet", "totalStockholderEquity"),
    "current_assets": ("Balance_Sheet", "totalCurrentAssets"),
    "current_liabilities": ("Balance_Sheet", "totalCurrentLiabilities"),
    "inventory": ("Balance_Sheet", "inventory"),
    "cash": ("Balance_Sheet", "cashAndEquivalents"),
    "short_term_investments": ("Balance_Sheet", "shortTermInvestments"),
    "total_debt": ("Balance_Sheet", "longTermDebtTotal"),
    "operating_cashflow": ("Cash_Flow", "totalCashFromOperatingActivities"),
    "capex": ("Cash_Flow", "capitalExpenditures"),
    "depreciation": ("Cash_Flow", "depreciationAndAmortization"),
    "free_cash_flow": ("Cash_Flow", "freeCashFlow"),
}

#: canonical item -> EODHD ``Highlights`` field (flat, current period only).
BULK_HIGHLIGHTS: dict[str, str] = {
    "market_cap": "MarketCapitalization",
    "shares_outstanding": "SharesOutstanding",
    "eps": "EarningsShare",
    "ebitda": "EBITDA",
    "revenue_ttm": "RevenueTTM",
    "gross_profit_ttm": "GrossProfitTTM",
    "net_income_ttm": "NetIncomeTTM",
    "return_on_equity": "ReturnOnEquityTTM",
    "return_on_assets": "ReturnOnAssetsTTM",
}


class BulkResult(NamedTuple):
    """One bulk request's outcome: the rows plus what it cost."""

    rows: dict
    requests: int
    api_calls: int
    symbols_requested: int


def _num(value) -> float | None:
    """Finite float or None - a vendor string number is still a number."""
    try:
        v = float(value)
    except (TypeError, ValueError):
        return None
    return v if math.isfinite(v) else None


def _dig(payload: dict, *path):
    """Walk a nested payload; None when any step is absent."""
    cur = payload
    for key in path:
        if isinstance(cur, dict):
            cur = cur.get(key)
        elif isinstance(cur, (list, tuple)) and isinstance(key, int):
            cur = cur[key] if 0 <= key < len(cur) else None
        else:
            return None
    return cur


def _statement_year(statement, index: int) -> dict:
    """The ``index``-th yearly period of a statement block (0 = newest).

    The vendor's own payload shape could not be read while writing this (the
    Extended Fundamentals plan is support-gated), so both documented shapes are
    accepted: a list of periods, or an object keyed by period end date (whose
    keys are sorted newest-first). Anything else is absent.
    """
    if isinstance(statement, (list, tuple)):
        if not 0 <= index < len(statement):
            return {}
        row = statement[index]
        return row if isinstance(row, dict) else {}
    if isinstance(statement, dict):
        keys = sorted((k for k in statement if k != "date"), reverse=True)
        if not 0 <= index < len(keys):
            return {}
        row = statement[keys[index]]
        return row if isinstance(row, dict) else {}
    return {}


def canonical_fin_from_bulk(payload: dict) -> dict:
    """Map one item of an EODHD bulk-fundamentals payload to canonical ``fin``.

    The canonical shape is the chain's own: a flow/stock item is either a flat
    float or ``{"current": .., "prior": ..}`` so the period-over-period legs
    (Piotroski's deleveraging, the growth factors) can run - see
    ``statement_parsing``. ``capex`` is normalised to a **positive magnitude**
    because ``ratios.compute_ratios`` subtracts ``abs(capex)``; the vendor
    reports it as a negative outflow. A field the payload does not carry is
    absent, never 0.
    """
    if not isinstance(payload, dict):
        return {}
    fin: dict = {}
    yearlies = _dig(payload, "Financials") or {}
    for canonical, (block, field) in BULK_YEARLY_STATEMENTS.items():
        series = _dig(yearlies, block, "yearly") if isinstance(yearlies, dict) else None
        cur = _num(_statement_year(series, 0).get(field))
        prior = _num(_statement_year(series, 1).get(field))
        if canonical == "capex":
            cur = abs(cur) if cur is not None else None
            prior = abs(prior) if prior is not None else None
        if cur is None and prior is None:
            continue
        fin[canonical] = {"current": cur, "prior": prior}
    for canonical, field in BULK_HIGHLIGHTS.items():
        v = _num(_dig(payload, "Highlights", field))
        if v is not None and canonical not in fin:
            fin[canonical] = v
    cash = _num(_dig(fin.get("cash"), "current")) if isinstance(fin.get("cash"), dict) else _num(fin.get("cash"))
    sti = _num(_dig(fin.get("short_term_investments"), "current")) if isinstance(fin.get("short_term_investments"), dict) else None
    if cash is not None:
        fin["cash_and_investments"] = cash + (sti or 0.0)
    # FCF is derived only when the vendor did not report it (and only from the
    # canonical legs, never from a generic proxy).
    fcf = _num(_dig(fin.get("free_cash_flow"), "current")) if isinstance(fin.get("free_cash_flow"), dict) else None
    if fcf is None:
        ocf = _num(_dig(fin.get("operating_cashflow"), "current")) if isinstance(fin.get("operating_cashflow"), dict) else None
        capex = _num(_dig(fin.get("capex"), "current")) if isinstance(fin.get("capex"), dict) else None
        if ocf is not None and capex is not None:
            fin["free_cash_flow"] = {"current": ocf - capex, "prior": None}
    sector = _dig(payload, "General", "Sector")
    if isinstance(sector, str) and sector:
        fin["sector"] = sector
    return fin


def panel_row_from_fin(ticker: str, fin: dict) -> dict:
    """The panel row for one name, from its canonical financials.

    The metric derivation is the peer-panel builder the ``FundamentalScore``
    sub-scores already consume (``peer_universe._panel_from_fin`` with
    ``include_score_metrics``), so the panel cannot disagree with the engine it
    measures. ``fcf_yield`` is the schema's own identity on the producer's
    published ratio (``1 / price_to_free_cash_flow``), not a second formula.
    """
    from tradingagents.strategies.peer_universe import _panel_from_fin

    row = dict(_panel_from_fin(str(ticker).upper(), fin, include_score_metrics=True))
    p_fcf = row.get("price_to_free_cash_flow")
    if _num(p_fcf) not in (None, 0.0) and _num(row.get("fcf_yield")) is None:
        row["fcf_yield"] = 1.0 / float(p_fcf)
    return row


def panel_row_from_bulk(ticker: str, payload: dict) -> dict:
    """One bulk payload item -> one panel row ({} when the payload is empty)."""
    fin = canonical_fin_from_bulk(payload)
    if not fin:
        return {}
    try:
        return panel_row_from_fin(ticker, fin)
    except Exception:  # noqa: BLE001 - a per-name derivation failure is a gap
        return {}


def _bulk_items(payload) -> dict[str, dict]:
    """Normalise a bulk response to ``{symbol: item}``.

    The vendor returns either an object keyed by symbol or a list of items each
    carrying its own symbol; both shapes are accepted because the live payload
    could not be read here (support-gated plan).
    """
    out: dict[str, dict] = {}
    if isinstance(payload, dict):
        for key, item in payload.items():
            if isinstance(item, dict):
                code = str(item.get("Code") or item.get("code") or key)
                out[code.split(".")[0].strip().upper()] = item
    elif isinstance(payload, (list, tuple)):
        for item in payload:
            if not isinstance(item, dict):
                continue
            code = item.get("Code") or item.get("code") or item.get("symbol")
            if code:
                out[str(code).split(".")[0].strip().upper()] = item
    return out


def eodhd_bulk_transport(*, exchange: str = "US", chunk_size: int = CHUNK_SIZE):
    """The live transport: chunked bulk-fundamentals requests, one per chunk.

    Injectable by design - the panel builder takes any
    ``transport(chunk, date) -> BulkResult``; the live one is the only thing
    this environment cannot exercise (the Extended Fundamentals plan is
    support-gated on the vendor side).
    """
    def _fetch(chunk, date):  # noqa: ARG001 - the date is the cache key, not a param
        from tradingagents.dataflows.eodhd import _eodhd_get

        codes = [str(c).upper() for c in chunk]
        query = ",".join(codes if "." in c else f"{c}.US" for c in codes)
        payload = _eodhd_get(f"bulk-fundamentals/{exchange}", {"fmt": "json", "symbols": query})
        items = _bulk_items(payload)
        rows = {}
        for code in codes:
            item = items.get(code.split(".")[0])
            if not item:
                continue
            row = panel_row_from_bulk(code.split(".")[0], item)
            if row:
                rows[code.split(".")[0]] = row
        return BulkResult(
            rows=rows,
            requests=1,
            api_calls=BULK_REQUEST_CALLS + PER_SYMBOL_CALLS * len(codes),
            symbols_requested=len(codes),
        )

    return _fetch


# ---------------------------------------------------------------------------
# The price leg
# ---------------------------------------------------------------------------


class PriceProvider:
    """Bars up to a date, from one fetch per ticker (the run's own chain).

    ``_ohlcv`` returns the most recent bars, so a historical panel needs the
    series sliced at the panel's date. One fetch per name, cached for the run,
    and every date is a slice of that same series - no per-date vendor call.

    The loader is captured **as a function object at construction**, because
    ``technical_rows_asof`` rebinds ``analysis_tools._ohlcv`` to read bars from
    this provider: looking the attribute up at call time would find that patch
    and recurse. (Found by a live run - the stub-loader tests could not see it.)
    """

    def __init__(self, loader=None, max_bars: int = 400):
        if loader is None:
            from tradingagents.agents.utils import analysis_tools as at

            loader = at._ohlcv
        self._loader = loader
        self._max_bars = max(30, int(max_bars))
        self._series: dict[str, dict] = {}

    def series(self, ticker: str) -> dict:
        key = str(ticker).upper()
        if key not in self._series:
            try:
                self._series[key] = self._loader(key) or {}
            except Exception:  # noqa: BLE001 - a missing name is a gap, not a crash
                self._series[key] = {}
        return self._series[key]

    def bars(self, ticker: str, date: str) -> dict:
        return slice_bars(self.series(ticker), date, self._max_bars)


_ISO_DATE_RE = __import__("re").compile(r"^\d{4}-\d{2}-\d{2}")


def slice_bars(series: dict, date: str, max_bars: int = 400) -> dict:
    """The bars of ``series`` up to ``date`` (dates are compared as ISO text).

    A bar list whose dates are not ISO-ordered cannot be sliced honestly, so
    the slice is returned empty rather than guessed at.
    """
    if not isinstance(series, dict):
        return {}
    dates = list(series.get("dates") or [])
    closes = list(series.get("closes") or [])
    if not dates or len(closes) != len(dates):
        return {}
    # A date that is not an ISO calendar date cannot be compared against one:
    # `"1" <= "2026-09-01"` is True, so an unvalidated series would be "sliced"
    # by a string comparison that means nothing. Refuse rather than guess.
    if any(not _ISO_DATE_RE.match(str(d)) for d in dates):
        return {}
    if not _ISO_DATE_RE.match(str(date)):
        return {}
    keep = [i for i, d in enumerate(dates) if str(d)[:10] <= str(date)[:10]]
    if not keep:
        return {}
    if max_bars and len(keep) > max_bars:
        keep = keep[-max_bars:]
    out: dict = {"dates": [], "closes": [], "highs": [], "lows": [], "volumes": [], "opens": []}
    for field in out:
        vals = list(series.get(field) or [])
        if len(vals) != len(dates):
            out[field] = []
            continue
        out[field] = [vals[i] for i in keep]
    return out


def technical_rows_asof(tickers, date: str, provider: PriceProvider) -> dict[str, dict]:
    """The ``TechnicalScore`` components of each name, as of ``date``.

    The assembly is the run's own ``analysis_tools._technical_components`` - the
    one implementation of "component -> producer" - and this function only
    substitutes where it reads its bars from, so the panel cannot drift from the
    engine it measures. No second assembly, no re-derived formula.
    """
    from tradingagents.agents.utils import analysis_tools as at

    saved = at._ohlcv
    at._ohlcv = lambda ticker, days=320: provider.bars(ticker, date)  # noqa: ARG005
    try:
        rows: dict[str, dict] = {}
        for t in tickers:
            code = str(t).upper()
            try:
                comps = at._technical_components(code) or {}
            except Exception:  # noqa: BLE001 - one name's failure is one gap
                comps = {}
            if comps:
                rows[code] = dict(comps)
        return rows
    finally:
        at._ohlcv = saved


def closes_asof(tickers, date: str, provider: PriceProvider) -> dict[str, float]:
    """Each name's close at ``date`` (the forward-return leg of the stats)."""
    out: dict[str, float] = {}
    for t in tickers:
        code = str(t).upper()
        bars = provider.bars(code, date)
        closes = bars.get("closes") or []
        v = _num(closes[-1]) if closes else None
        if v is not None:
            out[code] = v
    return out


# ---------------------------------------------------------------------------
# Building the panel
# ---------------------------------------------------------------------------


def build_panel(
    dates,
    universe,
    *,
    transport=None,
    price_provider: PriceProvider | None = None,
    cache_dir: str | None = None,
    chunk_size: int = CHUNK_SIZE,
    technical: bool = True,
    fetched_at: str | None = None,
) -> dict:
    """Build (or load) one panel file per date; never re-fetch a cached date.

    Returns the build record: the per-date outcome, the **cost** (requests and
    API calls actually spent), the **coverage** (names requested vs present,
    metrics measured) and the panel-level label from
    ``alpha_health.cross_section_status``. ``transport`` and ``price_provider``
    are the two injectable legs; with both ``None`` the call is a pure cache
    read.
    """
    cache_dir = cache_dir or default_cache_dir()
    dates = [str(d) for d in (dates or []) if str(d).strip()]
    universe_all = [str(t).upper() for t in (universe or []) if str(t).strip()]
    chunks = split_chunks(universe_all, chunk_size)
    stamp = fetched_at or datetime.now(timezone.utc).isoformat(timespec="seconds")

    cost = {"requests": 0, "api_calls": 0, "chunks": 0, "symbols_requested": 0,
            "cache_hits": 0, "dates_fetched": 0, "estimate": estimate_cost(len(universe_all), chunk_size=chunk_size),
            "fetched_at": stamp}
    per_date: dict = {}
    for date in dates:
        path = panel_path(cache_dir, date)
        cached = read_panel(path)
        if cached is not None:
            rows, meta = cached
            cost["cache_hits"] += 1
            per_date[date] = {
                "path": path, "source": "cache", "n_names": len(rows),
                "n_metrics": sum(len(r) for r in rows.values()),
                "symbols_requested": (meta or {}).get("symbols_requested", len(universe_all)),
                "shares": 0.0,
                "fetched_at": (meta or {}).get("fetched_at"),
                "cost": (meta or {}).get("cost"),
            }
            continue
        rows: dict = {}
        wanted = 0
        fundamentals_error: str | None = None
        if transport is not None:
            for chunk in chunks:
                try:
                    res = transport(chunk, date)
                except Exception as exc:  # noqa: BLE001 - the vendor gate is a finding
                    # A transport failure is the vendor-gate finding the plan
                    # asks to record (P0-2: the Extended Fundamentals plan is
                    # support-gated), not a crash: the rest of the panel - the
                    # technical leg - still builds, and the reason is written
                    # into the file so no reader mistakes it for a thin market.
                    fundamentals_error = f"{type(exc).__name__}: {exc}"
                    break
                wanted += int(res.symbols_requested)
                cost["requests"] += int(res.requests)
                cost["api_calls"] += int(res.api_calls)
                cost["chunks"] += 1
                cost["symbols_requested"] += int(res.symbols_requested)
                for code, row in (res.rows or {}).items():
                    if row:
                        rows.setdefault(str(code).upper(), {}).update(row)
        if fundamentals_error:
            cost.setdefault("errors", []).append(
                {"date": date, "leg": "fundamentals", "error": fundamentals_error}
            )
        if price_provider is not None:
            if technical:
                for code, comps in technical_rows_asof(universe_all, date, price_provider).items():
                    rows.setdefault(code, {}).update(comps)
            for code, close in closes_asof(universe_all, date, price_provider).items():
                rows.setdefault(code, {})["close"] = close
        meta = {
            "date": date,
            "fetched_at": stamp,
            "symbols_requested": wanted or len(universe_all),
            "n_names": len(rows),
            "n_metrics": sum(len(r) for r in rows.values()),
            "cost": {
                "requests": cost["requests"],
                "api_calls": cost["api_calls"],
                "model": cost["estimate"]["model"],
            },
            "legs": {
                "fundamentals": (
                    "eodhd bulk-fundamentals" if transport is not None
                    and not fundamentals_error else
                    (fundamentals_error or "not fetched")
                ),
                "technical": (
                    "analysis_tools._technical_components on bars up to the date"
                    if (price_provider is not None and technical) else "not fetched"
                ),
            },
            "vendor_gate": fundamentals_error,
            "basis": (
                "cross-sectional panel for one trading date; metrics are the "
                "score engines' own component names, NA when a producer could "
                "not measure (never 0). EODHD Extended Fundamentals is "
                "support-gated: the live fetch is unverified."
            ),
        }
        if not rows:
            # An empty fetch is NOT a panel: caching it would turn one vendor
            # failure into a permanent "cached" date. The date stays unfetched
            # (and is retried) instead.
            per_date[date] = {
                "path": path, "source": "empty-fetch", "n_names": 0, "n_metrics": 0,
                "symbols_requested": wanted or len(universe_all), "fetched_at": stamp,
                "cost": None, "vendor_gate": fundamentals_error,
            }
            continue
        write_panel(path, rows, meta)
        cost["dates_fetched"] += 1
        per_date[date] = {
            "path": path, "source": "fetched", "n_names": len(rows),
            "n_metrics": meta["n_metrics"], "symbols_requested": meta["symbols_requested"],
            "fetched_at": stamp, "cost": meta["cost"],
            "vendor_gate": fundamentals_error,
        }

    names_by_date = [per_date[d]["n_names"] for d in dates]
    present = sum(names_by_date)
    status = alpha_health.cross_section_status(names_by_date)
    coverage = {
        "dates": len(dates),
        "names_requested": len(universe_all),
        "names_present": max(names_by_date) if names_by_date else 0,
        "names_by_date": dict(zip(dates, names_by_date, strict=False)),
        "metric_cells": sum(per_date[d]["n_metrics"] for d in dates),
        "ratio": (present / (len(dates) * len(universe_all))
                  if dates and universe_all else None),
    }
    return {
        "cache_dir": cache_dir,
        "dates": dates,
        "universe": universe_all,
        "universe_n": len(universe_all),
        "chunks": len(chunks),
        "chunk_size": int(chunk_size),
        "per_date": per_date,
        "cost": cost,
        "coverage": coverage,
        "status": status["status"],
        "status_reason": status["reason"],
        "floors": status["floors"],
        "observed": status["observed"],
        "vendor_gate": next(
            (d["vendor_gate"] for d in per_date.values() if d.get("vendor_gate")), None
        ),
        "basis": (
            f"panel build: {len(dates)} date(s) x {len(universe_all)} symbol(s) in "
            f"{len(chunks)} chunk(s); cached dates are never re-fetched "
            f"({cost['cache_hits']} cache hit(s) this run)"
        ),
    }


def load_panel_series(dates, universe, *, cache_dir: str | None = None) -> dict:
    """Load the cached panels for ``dates``: ``{date: {ticker: {metric: value}}}``.

    The evaluate-only path - no transport, no price provider, no network.
    """
    cache_dir = cache_dir or default_cache_dir()
    out: dict = {}
    for date in [str(d) for d in (dates or [])]:
        cached = read_panel(panel_path(cache_dir, date))
        if cached is None:
            continue
        rows, _meta = cached
        if universe:
            keep = {str(t).upper() for t in universe}
            rows = {t: r for t, r in rows.items() if t in keep}
        out[date] = rows
    return out


# ---------------------------------------------------------------------------
# Which engines exist, and what each one declares
# ---------------------------------------------------------------------------

#: The engines of the deliverable map (plan section 1.1), with their module.
ENGINE_MODULES: tuple[tuple[str, str], ...] = (
    ("fundamental_score", "tradingagents.strategies.fundamental_score"),
    ("technical_score", "tradingagents.strategies.technical_score"),
    ("regime_score", "tradingagents.strategies.regime_score"),
    ("risk_score", "tradingagents.strategies.risk_score"),
    ("news_score", "tradingagents.strategies.news_score"),
    ("sentiment_score", "tradingagents.strategies.sentiment_score"),
)

#: EventScore is a *state*, not a scored engine (plan section 8, master 1.4).
ENGINE_NOT_SCORED: dict[str, str] = {
    "event_state": (
        "EventScore is a state/flag object, not a 0-100 score (master rule: four "
        "output types stay four); the panel measures scores and takes no "
        "position on the event state"
    ),
}


def _import_module(path: str):
    """Import a dotted module path, or raise the ImportError it raised."""
    import importlib

    return importlib.import_module(path)


def _declared_components(mod) -> dict[str, dict]:
    """The module's declared component table, in a shape the panel can read.

    ``COMPONENTS`` is the kernel's shape (`technical_score`): a mapping of name
    to an object carrying ``category`` / ``direction``. A sibling engine that
    declares a plain name tuple is read as well; anything else is reported as
    "no declared component table" rather than guessed at.
    """
    comps = getattr(mod, "COMPONENTS", None)
    out: dict[str, dict] = {}
    if isinstance(comps, dict):
        for name, spec in comps.items():
            out[str(name)] = {
                "category": str(getattr(spec, "category", "") or ""),
                "direction": str(getattr(spec, "direction", "") or ""),
                "producer": str(getattr(spec, "producer", "") or ""),
            }
    elif isinstance(comps, (list, tuple)):
        out = {str(n): {"category": "", "direction": "", "producer": ""} for n in comps}
    return out


def _declared_categories(mod) -> dict[str, dict]:
    """``{category: {"weight": w, "components": (...)}}`` from the module."""
    weights = getattr(mod, "CATEGORY_WEIGHTS", None) or {}
    members = getattr(mod, "CATEGORY_COMPONENTS", None) or {}
    out: dict[str, dict] = {}
    for cat in weights or {}:
        out[str(cat)] = {
            "weight": _num(weights[cat]),
            "components": tuple(members.get(cat) or ()),
        }
    return out


def engine_registry() -> dict[str, dict]:
    """Every engine of the deliverable map, and what this layer can read.

    ``available`` is a statement about the tree, not about the data: an engine
    whose module does not exist is reported with its reason so the findings
    document can record `UNMEASURED` for it instead of silently omitting it.
    """
    registry: dict[str, dict] = {}
    for name, module_path in ENGINE_MODULES:
        entry: dict = {"module": module_path}
        try:
            mod = _import_module(module_path)
        except Exception as exc:  # noqa: BLE001 - absence is a finding, not a crash
            registry[name] = {
                **entry,
                "available": False,
                "reason": f"{type(exc).__name__}: {exc}",
            }
            continue
        factors: dict[str, dict] = {}
        if name == "fundamental_score":
            from tradingagents.strategies.factor_schema import SUBSCORE_FACTORS

            for sub, names in SUBSCORE_FACTORS.items():
                for f in names:
                    factors[str(f)] = {"category": str(sub), "direction": "", "producer": ""}
        for fname, spec in _declared_components(mod).items():
            factors[fname] = spec
        registry[name] = {
            **entry,
            "available": bool(factors),
            "reason": ("" if factors else
                       "module imports but declares no component table this "
                       "layer can read (COMPONENTS / SUBSCORE_FACTORS)"),
            "factors": factors,
            "categories": _declared_categories(mod),
        }
    for name, reason in ENGINE_NOT_SCORED.items():
        registry[name] = {"module": "", "available": False, "reason": reason,
                          "factors": {}, "categories": {}}
    return registry


#: The two blocks the plan names, with the sentence that names them.
REDUNDANCY_BLOCKS: dict[str, dict] = {
    "technical_trend_momentum_relative_strength": {
        "engine": "technical_score",
        "categories": ("trend", "momentum", "relative_strength"),
        "weight_share": 50.0,
        "reason": (
            "plan section 7: TechnicalScore puts 50% of its weight on trend + "
            "momentum + relative strength, which are correlated by construction "
            "(the evidence ledger: trend filters, MA rules and TSMOM harvest one "
            "latent factor)"
        ),
    },
    "fundamental_fcf_yield_cluster": {
        "engine": "fundamental_score",
        "factors": (
            "fcf_yield",
            "price_to_free_cash_flow",
            "price_to_cash_flow",
            "earnings_yield",
            "val_z",
        ),
        "weight_share": None,
        "reason": (
            "plan section 7: FundamentalScore's FCF-yield / price-FCF / "
            "normalized-FCF-yield / earnings-yield cluster is the same problem "
            "as the technical block"
        ),
    },
}


def block_members(block: dict, registry: dict) -> list[str]:
    """The block's declared member names (categories expanded to components)."""
    if "factors" in block:
        return [str(f) for f in block["factors"]]
    engine = registry.get(block.get("engine") or "") or {}
    cats = set(block.get("categories") or ())
    factors = engine.get("factors") or {}
    members = [f for f, spec in factors.items() if spec.get("category") in cats]
    return sorted(members)


# ---------------------------------------------------------------------------
# Series, statistics, multiple testing
# ---------------------------------------------------------------------------


def to_scores(panels: dict, dates, metric: str) -> dict:
    """``{date: {ticker: value}}`` for one metric (the harness' own input)."""
    out: dict = {}
    for date in dates:
        row_map = panels.get(date) or {}
        vals = {
            str(t).upper(): float(r[metric])
            for t, r in row_map.items()
            if isinstance(r, dict) and _num(r.get(metric)) is not None
        }
        if vals:
            out[str(date)] = vals
    return out


def to_prices(panels: dict, dates) -> dict:
    """``{ticker: [close per date]}`` aligned to ``sorted(score dates)``."""
    ordered = sorted(d for d in dates if d in panels)
    out: dict = {}
    for date in ordered:
        for t, r in (panels.get(date) or {}).items():
            if isinstance(r, dict):
                out.setdefault(str(t).upper(), []).append(_num(r.get("close")))
    return out


def observation_matrix(panels: dict, dates, metrics) -> dict:
    """``{obs_key: {metric: value}}`` - one row per (date, ticker) observation."""
    obs: dict = {}
    for date in dates:
        for ticker, row in (panels.get(date) or {}).items():
            if not isinstance(row, dict):
                continue
            key = f"{date}|{str(ticker).upper()}"
            vals = {m: float(row[m]) for m in metrics if _num(row.get(m)) is not None}
            if vals:
                obs[key] = vals
    return obs


def period_series(scores: dict, prices: dict, *, holding: int, n_buckets: int,
                  min_names: int = 4) -> dict:
    """The per-period series the multiple-testing checks need.

    ``rank_ic`` comes from ``sentiment_research.rolling_information_coefficient``
    (the harness' own IC producer); ``spread`` is the per-period top-minus-bottom
    bucket forward return, built from the harness' own primitives
    (``_cross_section`` / ``_bucket`` / ``_forward_returns``) and nothing else.
    """
    from tradingagents.strategies.sentiment_research import (
        _bucket,
        _cross_section,
        _forward_returns,
        rolling_information_coefficient,
    )

    dates = sorted(scores)
    panel = {
        t: [(scores.get(d) or {}).get(t) for d in dates]
        for t in sorted({t for d in dates for t in (scores.get(d) or {})})
    }
    n_ret, fwd = _forward_returns(panel, prices, holding)
    spreads: list[float] = []
    for i in range(max(0, n_ret - holding)):
        sig = _cross_section(panel, i)
        cs = _cross_section(fwd, i)
        names = [t for t in sig if t in cs and cs[t] is not None]
        if len(names) < min_names:
            continue
        xs = [sig[t] for t in names]
        buckets: dict[int, list[float]] = {}
        for t in names:
            buckets.setdefault(_bucket(sig[t], xs, n_buckets), []).append(cs[t])
        lo = buckets.get(0)
        hi = buckets.get(n_buckets - 1)
        if not lo or not hi:
            continue
        spreads.append(sum(hi) / len(hi) - sum(lo) / len(lo))
    ics: list[float] = []
    try:
        res = rolling_information_coefficient(panel, prices, holding=holding,
                                              min_assets=min_names)
        ics = [float(v) for v in ((res or {}).get("rank_ic") or [])]
    except (ValueError, ZeroDivisionError, KeyError):
        ics = []
    return {"rank_ic": ics, "spread": spreads}


def multiple_testing(series: dict, *, n_trials: int, train_frac: float = OOS_TRAIN_FRAC,
                     cpcv_splits: int = 5, embargo: int = 0, seed: int = 0) -> dict:
    """The OOS split and the multiple-testing checks for ONE factor's series.

    * the **OOS split** uses ``evaluate.oos_split`` on the per-period rank IC so
      the cut is the existing implementation's, not a second one;
    * ``deflated_sharpe`` penalises the spread series by the size of the trial
      family (the number of factors measured together);
    * ``purged_cpcv_splits`` + ``cpcv_overfit_mask`` cut the period index into
      combinatorial purged folds and report whether the best in-sample fold
      fails out of sample;
    * ``pbo_flag`` is family-level and is applied by ``evaluate_panel``.
    """
    ics = list(series.get("rank_ic") or [])
    spreads = list(series.get("spread") or [])
    out: dict = {"n_periods_ic": len(ics), "n_periods_spread": len(spreads)}

    oos_train, oos_test = evaluate.oos_split(ics, ics, train_frac)
    cut = len(ics) - len(oos_test)
    train_mean = (sum(ics[:cut]) / cut) if cut else None
    oos_mean = (sum(oos_test) / len(oos_test)) if oos_test else None
    if train_mean is None or oos_mean is None:
        label, label_reason = "UNMEASURED", "one of the two bands is empty"
    elif train_mean == 0.0 or oos_mean == 0.0:
        label, label_reason = "FLAT", "a band's mean rank IC is exactly zero"
    elif (train_mean > 0.0) == (oos_mean > 0.0):
        label, label_reason = "SIGN_HOLDS", "the two bands agree in sign"
    else:
        label, label_reason = "SIGN_FLIPS", "the two bands disagree in sign"
    out["oos"] = {
        "train_frac": float(train_frac),
        "train_periods": cut,
        "oos_periods": len(oos_test),
        "train_mean_rank_ic": train_mean,
        "oos_mean_rank_ic": oos_mean,
        "label": label,
        "label_reason": label_reason,
        "basis": (
            "evaluate.oos_split on the per-period rank IC series "
            f"(train_frac={train_frac}); the label is a SIGN AGREEMENT between the "
            "train and OOS bands, not a significance test, and a stable NEGATIVE "
            "IC is a signal (its favourable direction is the opposite sign), not "
            "a failure"
        ),
    }

    if len(spreads) >= 2:
        # `periods_per_year=1`: the spread series is a PER-PERIOD long-short
        # return of a portfolio re-formed every period, so annualizing it (the
        # function's default 252) compounds a 12%/period spread into 4e12/yr and
        # makes the ratio unreadable. The period units are stated in the basis,
        # and the trials penalty is applied in the same units.
        dsr = evaluate.deflated_sharpe(spreads, n_trials=max(1, int(n_trials)),
                                       periods_per_year=1.0)
        mean = sum(spreads) / len(spreads)
        var = sum((s - mean) ** 2 for s in spreads) / (len(spreads) - 1)
        sd = math.sqrt(var)
        note = None
        if not isinstance(dsr, float) or not math.isfinite(dsr):
            # A decile long-short SPREAD is not a return series: it can lose
            # more than 100% of notional in one period, and the Sharpe inside
            # the DSR then has no real value. Withheld with the reason rather
            # than printed as a complex number (see `evaluate.cagr`).
            note = (
                "deflated Sharpe withheld: the spread series' compounded return "
                "is at or below -100%, so its growth rate is not a real number"
            )
            dsr = None
        elif sd < DSR_MIN_DISPERSION:
            # The Sharpe inside the DSR divides by this dispersion: at float
            # noise the ratio explodes and the number stops being a measurement.
            note = (
                f"the spread series' dispersion ({sd:.3g}) is at float noise "
                f"level (< {DSR_MIN_DISPERSION:g}); the deflated Sharpe is not "
                "interpretable"
            )
        out["deflated_sharpe"] = {
            "value": dsr,
            "n_trials": max(1, int(n_trials)),
            "mean_spread": mean,
            "stdev_spread": sd,
            "note": note,
            "basis": (
                "evaluate.deflated_sharpe on the per-period decile-spread series, "
                f"penalised by the number of factors measured in one panel "
                f"(n_trials={max(1, int(n_trials))}); periods_per_year=1 because the "
                "series is a per-period long-short return, and the series' own mean "
                "and dispersion are printed beside it because the ratio divides by "
                "the dispersion"
            ),
        }
    else:
        out["deflated_sharpe"] = {"value": None, "n_trials": max(1, int(n_trials)),
                                 "mean_spread": None, "stdev_spread": None, "note": None,
                                 "reason": f"{len(spreads)} spread period(s) measured"}

    ipcs: list[float] = []
    oopcs: list[float] = []
    folds = 0
    for train_idx, test_idx in evaluate.purged_cpcv_splits(
        len(spreads), n_splits=int(cpcv_splits), embargo=int(embargo)
    ):
        tr = [spreads[i] for i in train_idx if 0 <= i < len(spreads)]
        te = [spreads[i] for i in test_idx if 0 <= i < len(spreads)]
        if not tr or not te:
            continue
        ipcs.append(sum(tr) / len(tr))
        oopcs.append(sum(te) / len(te))
        folds += 1
    out["cpcv"] = {
        "n_splits": int(cpcv_splits),
        "embargo": int(embargo),
        "n_folds": folds,
        "overfit_mask": evaluate.cpcv_overfit_mask(ipcs, oopcs),
        "mean_ipc": (sum(ipcs) / len(ipcs)) if ipcs else None,
        "mean_oopc": (sum(oopcs) / len(oopcs)) if oopcs else None,
        "basis": (
            "evaluate.purged_cpcv_splits over the period index x "
            "cpcv_overfit_mask on the per-fold train/OOS spread means"
        ),
    }
    out["seed"] = int(seed)
    return out


def factor_statistics(scores: dict, prices: dict, *, holding: int, n_buckets: int,
                      n_trials: int, min_names: int = 4, min_obs: int = 5,
                      train_frac: float = OOS_TRAIN_FRAC, cpcv_splits: int = 5,
                      embargo: int = 0, seed: int = 0) -> dict:
    """One factor's full row set: the harness rows + OOS + multiple testing."""
    rows = alpha_health.score_evaluation_rows(
        scores, prices, holding=holding, n_buckets=n_buckets,
        min_names=min_names, min_obs=min_obs,
    )
    series = period_series(scores, prices, holding=holding, n_buckets=n_buckets,
                           min_names=min_names)
    return {
        "rows": rows,
        "series": series,
        "multiple_testing": multiple_testing(
            series, n_trials=n_trials, train_frac=train_frac,
            cpcv_splits=cpcv_splits, embargo=embargo, seed=seed,
        ),
        "status": STATUS_ADVISORY,
        "panel_status": rows.get("status"),
        "status_reason": rows.get("status_reason"),
        "ic_label": alpha_health.ic_label(
            ((rows.get("ic") or {}).get("mean_rank_ic"))
        ),
    }


# ---------------------------------------------------------------------------
# The redundancy matrix
# ---------------------------------------------------------------------------


def _pairs(values_by_metric: dict, min_pairs: int = MIN_PAIRS) -> dict:
    """Pairwise Spearman + Pearson over a shared observation set."""
    from tradingagents.strategies.alpha_health import _pearson, _rank_avg

    names = sorted(values_by_metric)
    out: dict = {}
    for i, a in enumerate(names):
        for b in names[i + 1:]:
            va, vb = values_by_metric[a], values_by_metric[b]
            common = sorted(set(va) & set(vb))
            if len(common) < int(min_pairs):
                continue
            xa = [va[k] for k in common]
            xb = [vb[k] for k in common]
            sp = _pearson(_rank_avg(xa), _rank_avg(xb))
            pe = _pearson(xa, xb)
            out[f"{a}|{b}"] = {
                "spearman": sp, "pearson": pe, "n": len(common),
                "abs_spearman": abs(sp) if sp is not None else None,
                "redundant": bool(sp is not None and abs(sp) >= REDUNDANT_ABS_CORR),
            }
    return out


def redundancy_matrix(observations: dict, metrics, *, min_pairs: int = MIN_PAIRS) -> dict:
    """``{metric: {obs_key: value}}`` -> the pairwise correlation matrix."""
    values_by_metric: dict = {}
    for metric in metrics:
        series = {k: v[metric] for k, v in observations.items() if metric in v}
        if len(series) >= int(min_pairs):
            values_by_metric[str(metric)] = series
    pairs = _pairs(values_by_metric, min_pairs)
    return {
        "n_metrics": len(metrics),
        "n_measured": len(values_by_metric),
        "n_pairs": len(pairs),
        "min_pairs": int(min_pairs),
        "redundant_abs_corr": REDUNDANT_ABS_CORR,
        "pairs": pairs,
        "basis": (
            "pairwise Spearman (reported) and Pearson (beside it) over the shared "
            "(date, ticker) observations of every measured metric; a pair below "
            f"min_pairs={int(min_pairs)} common observations is withheld, and "
            f"|Spearman| >= {REDUNDANT_ABS_CORR} is flagged as one bet rather than "
            "two (declared policy, printed, not measured)"
        ),
    }


def block_report(matrix: dict, *, registry: dict, measured=None) -> dict:
    """The two named blocks, with the pairwise correlations that decide them."""
    pairs = matrix.get("pairs") or {}
    measured_set = set(str(m) for m in (measured or []))
    out: dict = {}
    for block_name, block in REDUNDANCY_BLOCKS.items():
        members = block_members(block, registry)
        mset = set(members)
        block_pairs = {k: pairs[k] for k in sorted(pairs) if set(k.split("|")) <= mset}
        abs_vals = [v["abs_spearman"] for v in block_pairs.values()
                    if v["abs_spearman"] is not None]
        present = [m for m in members if m in measured_set]
        strongest = sorted(
            ({"pair": k, "spearman": v["spearman"], "n": v["n"],
              "redundant": v.get("redundant")} for k, v in block_pairs.items()),
            key=lambda r: -abs(r["spearman"] or 0.0),
        )[:5]
        out[block_name] = {
            "reason": block.get("reason"),
            "engine": block.get("engine"),
            "weight_share": block.get("weight_share"),
            "members": members,
            "measured": present,
            "missing": [m for m in members if m not in measured_set],
            "pairs": block_pairs,
            "n_pairs": len(block_pairs),
            # The strongest pairs travel with their `n`: a |rho| of 1.0 over 16
            # observations is not the same claim as one over 4,000.
            "strongest_pairs": strongest,
            "max_abs_spearman": max(abs_vals) if abs_vals else None,
            "mean_abs_spearman": (sum(abs_vals) / len(abs_vals)) if abs_vals else None,
            "redundant_pairs": sorted(k for k, v in block_pairs.items() if v.get("redundant")),
        }
    return out


# ---------------------------------------------------------------------------
# Per-engine findings and the weight vector
# ---------------------------------------------------------------------------


def engine_weight_vector(engine: str, registry: dict) -> dict:
    """The engine's OWN declared weight vector, with its provenance.

    No vector is invented here (master rule 6): the engine's own table is read
    and printed, the sub-score composite that ships equal-weight says so, and an
    engine with no wheel table gets ``None`` and the reason.
    """
    entry = registry.get(engine) or {}
    if engine == "fundamental_score":
        return {
            "weights": {"FQS": 0.25, "FGS": 0.25, "VS": 0.25, "FRS": 0.25},
            "status": STATUS_RESEARCH_ONLY,
            "panel_status": alpha_health.CROSS_SECTION_OK,
            "basis": (
                "equal weights (1/4 each; no validated vector published - the "
                "engine prints the same fact in its own basis)"
            ),
        }
    cats = entry.get("categories") or {}
    weights = {c: v.get("weight") for c, v in cats.items() if v.get("weight") is not None}
    if not weights:
        return {"weights": None, "status": "UNMEASURED",
                "basis": f"no declared category weight table on {engine}"}
    total = sum(float(w) for w in weights.values()) or 1.0
    return {
        "weights": weights,
        "status": STATUS_RESEARCH_ONLY,
        "panel_status": alpha_health.CROSS_SECTION_OK,
        "share": {c: float(w) / total for c, w in weights.items()},
        "basis": (
            f"the engine's own declared table (CATEGORY_WEIGHTS on "
            f"{entry.get('module')}), printed with its measured evidence beside "
            "it - the panel measures the table, it does not revise it"
        ),
    }


def category_findings(engine: str, registry: dict, factors: dict) -> dict:
    """Per-category verdicts from the measured rows: survive / redundant / drop.

    The rule is declared and printed: a factor is a **drop candidate** when its
    rank IC is `WEAK` by the harness' own label (`alpha_health.ic_label`, weak =
    0.03) or when it is flagged redundant with a stronger partner; a category
    **survives** when at least one of its factors is measured with a
    MODERATE/STRONG label and is not redundant. Nothing is dropped here - the
    weight table is the owner's; this is the evidence he revises it with.
    """
    entry = registry.get(engine) or {}
    declaration = entry.get("factors") or {}
    categories: dict[str, dict] = {}
    for factor, measured in factors.items():
        cat = (declaration.get(factor) or {}).get("category") or "(unassigned)"
        row = categories.setdefault(cat, {"measured": [], "unmeasured": [],
                                          "drop_candidates": [], "survived": [],
                                          "ic_unmeasured": [], "ic_labels": {}})
        if not measured.get("measured"):
            row["unmeasured"].append(factor)
            continue
        row["measured"].append(factor)
        label = measured.get("ic_label")
        row["ic_labels"][factor] = label
        if label in (None, "UNKNOWN"):
            # No IC was measured for this factor (a single cross-section, or a
            # series too short for a forward return): it is NOT a drop
            # candidate, it is unmeasured on that half of the evidence.
            row["ic_unmeasured"].append(factor)
        elif label == "WEAK" or measured.get("redundant"):
            row["drop_candidates"].append(factor)
        else:
            row["survived"].append(factor)
    for cat in (entry.get("categories") or {}):
        categories.setdefault(str(cat), {"measured": [], "unmeasured": [],
                                         "drop_candidates": [], "survived": [],
                                         "ic_unmeasured": [], "ic_labels": {}})
    for cat, row in categories.items():
        for key in ("measured", "unmeasured", "drop_candidates", "survived",
                    "ic_unmeasured"):
            row[key] = sorted(row[key])
        row["weight"] = ((entry.get("categories") or {}).get(cat) or {}).get("weight")
        has_ic = any(row["ic_labels"].get(f) not in (None, "UNKNOWN")
                     for f in row["measured"])
        redundant = [f for f in row["measured"] if factors.get(f, {}).get("redundant")]
        if not row["measured"]:
            row["verdict"] = "UNMEASURED"
        elif not has_ic:
            # The matrix spoke and the IC did not: say exactly that.
            row["verdict"] = "REDUNDANCY_ONLY" if redundant else "MATRIX_ONLY"
        elif row["survived"]:
            row["verdict"] = "SURVIVES"
        elif redundant:
            row["verdict"] = "REDUNDANT"
        else:
            row["verdict"] = "DROP_CANDIDATE"
        row["basis"] = (
            "survives = at least one factor measured with a MODERATE/STRONG rank IC "
            "(`alpha_health.ic_label`, weak=0.03) and not flagged redundant; "
            "redundant = a measured factor at |Spearman| >= "
            f"{REDUNDANT_ABS_CORR} with a stronger partner; REDUNDANCY_ONLY / "
            "MATRIX_ONLY = the cross-section was measured but no IC was (the "
            "verdict then rests on the redundancy matrix alone)"
        )
    return categories


# ---------------------------------------------------------------------------
# The report
# ---------------------------------------------------------------------------


def evaluate_panel(
    panels: dict,
    *,
    dates=None,
    registry: dict | None = None,
    holding: int = 5,
    n_buckets: int = 10,
    min_names: int = 4,
    min_obs: int = 5,
    train_frac: float = OOS_TRAIN_FRAC,
    cpcv_splits: int = 5,
    embargo: int = 0,
    seed: int = 0,
    n_boot: int = 500,
    engines=None,
) -> dict:
    """Measure every declared factor/component over the cached panel.

    Pure over ``panels`` (no network). Emits per-factor statistics, the
    redundancy matrix with its two named blocks, the per-engine findings and the
    weight vector - which is ``None`` whenever the panel is below the
    cross-section floors.
    """
    registry = registry or engine_registry()
    dates = [str(d) for d in (dates if dates is not None else sorted(panels))]
    panels = {d: (panels.get(d) or {}) for d in dates}
    engine_names = [e for e in (engines if engines is not None else registry)
                    if e in registry]

    declared: dict[str, dict] = {}
    for engine in engine_names:
        for factor, spec in ((registry.get(engine) or {}).get("factors") or {}).items():
            if factor in declared:
                continue
            declared[factor] = {"engine": engine, **spec}

    measured_names = sorted({
        str(m) for d in dates for row in (panels.get(d) or {}).values()
        if isinstance(row, dict) for m in row
    })
    # The matrix is over DECLARED FACTORS, not over every column the panel
    # happens to carry: `close` is the return leg and a price level, and a
    # correlation between two price levels is a scale comparison, not evidence
    # about two signals.
    measured_names = sorted(m for m in measured_names if m in declared)
    prices = to_prices(panels, dates)
    # The trial family is the set of factors the panel could actually measure:
    # a factor with no data never ran, so it never inflates the DSR penalty.
    tested = sorted(f for f in declared if to_scores(panels, dates, f))
    n_trials = max(1, len(tested))

    factors: dict[str, dict] = {}
    for factor in sorted(declared):
        scores = to_scores(panels, dates, factor)
        if not scores:
            factors[factor] = {
                "engine": declared[factor]["engine"],
                "category": declared[factor].get("category") or "",
                "measured": False,
                "reason": (
                    "no panel row carries this metric - the factor's producer is "
                    "not on the panel path (a bulk payload field or a series the "
                    "single snapshot does not carry)"
                ),
            }
            continue
        stats = factor_statistics(
            scores, prices, holding=holding, n_buckets=n_buckets, n_trials=n_trials,
            min_names=min_names, min_obs=min_obs, train_frac=train_frac,
            cpcv_splits=cpcv_splits, embargo=embargo, seed=seed,
        )
        factors[factor] = {
            "engine": declared[factor]["engine"],
            "category": declared[factor].get("category") or "",
            "measured": True,
            "status": STATUS_ADVISORY,
            "n_observations": sum(len(v) for v in scores.values()),
            **stats,
        }

    # --- the redundancy matrix and the two named blocks -------------------
    matrix = redundancy_matrix(observations=observation_matrix(panels, dates, measured_names),
                               metrics=measured_names)
    blocks = block_report(matrix, registry=registry, measured=measured_names)
    factor_pairs = matrix.get("pairs") or {}
    for factor, row in factors.items():
        if row.get("measured"):
            row["redundant_with"] = sorted(
                k for k, v in factor_pairs.items()
                if v.get("redundant") and factor in k.split("|")
            )
            row["redundant"] = bool(row["redundant_with"])

    # --- family-level PBO / reality check / SPA ---------------------------
    family = {
        "n_factors": n_trials,
        "pbo": _pbo(factors, n_trials),
        "reality_check": None,
        "spa": None,
    }
    spread_series = {
        f: [float(x) for x in (row.get("series") or {}).get("spread") or []]
        for f, row in factors.items() if row.get("measured")
    }
    spread_series = {k: v for k, v in spread_series.items() if len(v) >= 2}
    if len(spread_series) >= 2:
        n = min(len(v) for v in spread_series.values())
        candidates = {k: v[:n] for k, v in spread_series.items()}
        zero = [0.0] * n
        try:
            family["reality_check"] = evaluate.reality_check(
                candidates, zero, n_boot=int(n_boot), seed=seed)
            family["spa"] = evaluate.spa(candidates, zero, n_boot=int(n_boot), seed=seed)
        except (ValueError, ZeroDivisionError, KeyError):  # pragma: no cover
            family["reality_check"] = None
            family["spa"] = None
        family["basis"] = (
            "family-level multiple testing across the measured factors: PBO "
            "(evaluate.pbo_flag) on the train/OOS spread means, White's reality "
            "check and Hansen's SPA (evaluate.reality_check / spa) against a "
            f"zero benchmark, stationary bootstrap n_boot={int(n_boot)} seed={seed}"
        )

    # --- per-engine findings and the weight vector ------------------------
    per_engine: dict[str, dict] = {}
    allowed = True
    for engine in engine_names:
        entry = registry.get(engine) or {}
        subset = {f: r for f, r in factors.items() if r.get("engine") == engine}
        vector = engine_weight_vector(engine, registry)
        findings = category_findings(engine, registry, subset)
        if not entry.get("available"):
            vector = {"weights": None, "status": "UNMEASURED",
                      "basis": entry.get("reason")}
        per_engine[engine] = {
            "module": entry.get("module"),
            "available": bool(entry.get("available")),
            "reason": entry.get("reason") or "",
            "n_declared": len(entry.get("factors") or {}),
            "n_measured": sum(1 for r in subset.values() if r.get("measured")),
            "weight_vector": vector,
            "categories": findings if entry.get("available") else {},
            "unmeasured": sorted(f for f, r in subset.items() if not r.get("measured")),
        }
        if vector.get("weights") and not entry.get("available"):
            allowed = False

    status = alpha_health.cross_section_status(
        [len(panels.get(d) or {}) for d in dates]
    )
    weight_vector = {
        "produced": bool(status["status"] == alpha_health.CROSS_SECTION_OK),
        "status": STATUS_RESEARCH_ONLY,
        "panel_status": status["status"],
        "reason": status["reason"],
        "vectors": ({e: v["weight_vector"] for e, v in per_engine.items()
                     if v["weight_vector"].get("weights")}
                    if status["status"] == alpha_health.CROSS_SECTION_OK else None),
        "basis": (
            "the panel produces a weight vector ONLY over a sufficient "
            "cross-section (owner Q4, plan section 9 Phase C); the vectors it "
            "prints are the engines' own declared tables with their measured "
            "evidence beside them, labelled RESEARCH_ONLY"
        ),
    }

    return {
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "spec": "docs/scores/IMPLEMENTATION_PLAN.md section 7 (WP-10) / section 9 Phase C",
        "status": STATUS_ADVISORY,
        "panel": {
            "dates": dates,
            "n_dates": len(dates),
            "n_names": max((len(panels.get(d) or {}) for d in dates), default=0),
            "n_metrics": len(measured_names),
            "status": status["status"],
            "status_reason": status["reason"],
            "floors": status["floors"],
            "observed": status["observed"],
        },
        "parameters": {
            "holding": int(holding), "n_buckets": int(n_buckets),
            "min_names": int(min_names), "min_obs": int(min_obs),
            "train_frac": float(train_frac), "cpcv_splits": int(cpcv_splits),
            "embargo": int(embargo), "seed": int(seed), "n_boot": int(n_boot),
        },
        "harness_gate": HARNESS_GATE,
        "factors": factors,
        "redundancy": {**matrix, "blocks": blocks},
        "family": family,
        "engines": per_engine,
        "weight_vector": weight_vector,
        "basis": (
            "the measurement layer of the score set: the panel's own cost and "
            "coverage, the harness rows per factor, the OOS split and the "
            "multiple-testing checks, the redundancy matrix and the per-engine "
            "finding. No weight is invented and no gate, size or SCORE_BAND is "
            "read (docs/scores/IMPLEMENTATION_PLAN.md section 7)"
        ),
        "allowed": allowed,
    }


def _pbo(factors: dict, n_trials: int) -> dict:
    """``evaluate.pbo_flag`` over the family's train/OOS spread means."""
    train: list[float] = []
    test: list[float] = []
    names: list[str] = []
    for factor, row in sorted(factors.items()):
        if not row.get("measured"):
            continue
        spreads = [float(x) for x in (row.get("series") or {}).get("spread") or []]
        if len(spreads) < 2:
            continue
        oos = (row.get("multiple_testing") or {}).get("oos") or {}
        cut = int(oos.get("train_periods") or 0)
        cut = min(cut, len(spreads))
        if cut <= 0 or cut >= len(spreads):
            continue
        names.append(factor)
        train.append(sum(spreads[:cut]) / cut)
        test.append(sum(spreads[cut:]) / (len(spreads) - cut))
    if not train:
        return {"flag": False, "n_trials": int(n_trials), "measured": 0,
                "basis": "pbo_flag needs at least one factor with a train and an OOS band"}
    # The families' per-factor order must be the same for the best-IS index to
    # mean anything: both lists are built from the same sorted factor loop.
    return {
        "flag": bool(evaluate.pbo_flag(train, test)),
        "n_trials": int(n_trials),
        "measured": len(names),
        "per_factor": dict(zip(names, ({"train_spread": t, "oos_spread": o} for t, o in zip(train, test)), strict=False)),
        "basis": (
            "evaluate.pbo_flag: the factor with the best in-sample spread is "
            "checked for a negative out-of-sample spread, over the family "
            f"measured together (n_trials={int(n_trials)})"
        ),
    }


# ---------------------------------------------------------------------------
# Rendering
# ---------------------------------------------------------------------------


def render_text(report: dict, build: dict | None = None) -> str:
    """The human-readable block: cost, coverage, label, factors, blocks."""
    lines: list[str] = ["# Score panel (WP-10)", ""]
    if build is not None:
        cost = build.get("cost") or {}
        cov = build.get("coverage") or {}
        lines.append(
            f"panel: {len(build.get('dates') or [])} date(s) x "
            f"{build.get('universe_n')} symbol(s) in {build.get('chunks')} chunk(s); "
            f"status {build.get('status')}"
        )
        lines.append(
            f"cost: {cost.get('api_calls')} API call(s) over {cost.get('requests')} "
            f"request(s), {cost.get('chunks')} chunk(s), {cost.get('cache_hits')} "
            f"cache hit(s), {cost.get('dates_fetched')} date(s) fetched at "
            f"{cost.get('fetched_at')}; model: {(cost.get('estimate') or {}).get('model')}"
        )
        lines.append(
            f"coverage: {cov.get('names_present')} of {cov.get('names_requested')} "
            f"name(s), {cov.get('metric_cells')} metric cell(s), ratio "
            f"{cov.get('ratio')}"
        )
        lines.append(f"label: {build.get('status')} - {build.get('status_reason')}")
        if build.get("vendor_gate"):
            lines.append(
                "vendor gate: the fundamentals leg did not run - "
                f"{build['vendor_gate']} (recorded, not hidden: this is the "
                "support-gated EODHD Extended Fundamentals plan)"
            )
        lines.append("")
    panel = report.get("panel") or {}
    lines.append(
        f"panel label: {panel.get('status')} - {panel.get('status_reason')}"
    )
    wv = report.get("weight_vector") or {}
    lines.append(
        "weight vector: "
        + ("produced" if wv.get("produced") else "NONE (panel below the floors)")
    )
    lines.append("")
    lines.append("## Factors")
    for factor, row in sorted((report.get("factors") or {}).items()):
        if not row.get("measured"):
            lines.append(f"- {factor} [{row.get('engine')}]: UNMEASURED - {row.get('reason')}")
            continue
        rows = row.get("rows") or {}
        ic = rows.get("ic") or {}
        dec = rows.get("deciles") or {}
        stab = rows.get("stability") or {}
        turn = rows.get("turnover") or {}
        oos = (row.get("multiple_testing") or {}).get("oos") or {}
        lines.append(
            f"- {factor} [{row.get('engine')}/{row.get('category')}]: "
            f"n={row.get('n_observations')} "
            + (f"rank_ic={ic.get('mean_rank_ic')} ic_ir={ic.get('ic_ir')} "
               f"({row.get('ic_label')})" if ic.get("available") else
               f"IC withheld - {ic.get('reason')}")
        )
        lines.append(
            "    decile spread="
            + (f"{dec.get('spread')} ordering="
               f"{(dec.get('ordering') or {}).get('ordered_pairs')}/"
               f"{(dec.get('ordering') or {}).get('adjacent_pairs')}"
               if dec.get("available") else f"withheld - {dec.get('reason')}")
            + f" persistence={stab.get('persistence')} "
            + ("turnover=" + str(turn.get("mean_turnover")) if turn.get("available")
               else "turnover withheld - " + str(turn.get("reason")))
        )
        lines.append(
            f"    OOS[{oos.get('label')}] train={oos.get('train_mean_rank_ic')} "
            f"oos={oos.get('oos_mean_rank_ic')} "
            f"dsr={((row.get('multiple_testing') or {}).get('deflated_sharpe') or {}).get('value')} "
            f"cpcv_overfit="
            f"{((row.get('multiple_testing') or {}).get('cpcv') or {}).get('overfit_mask')}"
            + (f" redundant_with={','.join(row.get('redundant_with') or [])}"
               if row.get("redundant_with") else "")
        )
    blocks = (report.get("redundancy") or {}).get("blocks") or {}
    lines.append("")
    lines.append("## Redundancy blocks")
    for name, block in blocks.items():
        lines.append(
            f"- {name}: {block.get('n_pairs')} pair(s) measured, max|rho|="
            f"{block.get('max_abs_spearman')} mean|rho|={block.get('mean_abs_spearman')}, "
            f"redundant pairs: {block.get('redundant_pairs')}")
        for pair in block.get("strongest_pairs") or []:
            lines.append(
                f"    {pair['pair']}: rho={pair['spearman']} n={pair['n']}"
                + (" [redundant]" if pair.get("redundant") else "")
            )
        lines.append(f"    {block.get('reason')}")
    fam = report.get("family") or {}
    lines.append("")
    lines.append("## Family multiple testing")
    lines.append(f"- pbo: {fam.get('pbo')}")
    lines.append(f"- reality_check: {fam.get('reality_check')}")
    lines.append(f"- spa: {fam.get('spa')}")
    lines.append("")
    lines.append("## Engines")
    for engine, row in sorted((report.get("engines") or {}).items()):
        v = row.get("weight_vector") or {}
        lines.append(
            f"- {engine}: {row.get('n_measured')}/{row.get('n_declared')} factor(s) "
            f"measured; weights {'NONE' if not v.get('weights') else v.get('weights')} "
            f"[{v.get('status')}] - {v.get('basis')}"
        )
        for cat, c in sorted((row.get("categories") or {}).items()):
            lines.append(
                f"    {cat} (weight {c.get('weight')}): {c.get('verdict')} - "
                f"survived {c.get('survived')} drop {c.get('drop_candidates')} "
                f"unmeasured {len(c.get('unmeasured') or [])}"
            )
    lines.append("")
    lines.append(f"basis: {report.get('basis')}")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def _read_list(path: str | None, inline: str | None) -> list[str]:
    """Symbols/dates from a file (one per line, ``#`` comments) or an inline list."""
    out: list[str] = []
    if path:
        with open(path, encoding="utf-8") as fh:
            for line in fh:
                item = line.split("#", 1)[0].strip()
                if item:
                    out.append(item)
    if inline:
        out.extend(p.strip() for p in inline.split(",") if p.strip())
    return out


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dates", default=None, help="comma-separated trading dates")
    parser.add_argument("--dates-file", default=None, help="one date per line")
    parser.add_argument("--symbols", default=None, help="comma-separated universe")
    parser.add_argument("--symbols-file", default=None, help="one symbol per line")
    parser.add_argument("--cache-dir", default=None, help="default: data_cache_dir")
    parser.add_argument("--chunk-size", type=int, default=CHUNK_SIZE)
    parser.add_argument("--exchange", default="US",
                        help=("bulk exchange code (default US; the per-exchange "
                              f"codes are {', '.join(EXCHANGE_CODES)} - the "
                              "vendor 404s on the generic US code for the "
                              "snapshot variant)"))
    parser.add_argument("--holding", type=int, default=5)
    parser.add_argument("--buckets", type=int, default=10)
    parser.add_argument("--train-frac", type=float, default=OOS_TRAIN_FRAC)
    parser.add_argument("--cpcv-splits", type=int, default=5)
    parser.add_argument("--embargo", type=int, default=0)
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--n-boot", type=int, default=500)
    parser.add_argument("--no-technical", action="store_true",
                        help="skip the technical leg (fundamentals only)")
    parser.add_argument("--evaluate-only", action="store_true",
                        help="read cached panels; no fetch of any kind")
    parser.add_argument("--cost-only", action="store_true",
                        help="print the API-call estimate for the universe and exit")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)

    cache_dir = args.cache_dir or default_cache_dir()
    dates = [d[:10] for d in _read_list(args.dates_file, args.dates)]
    universe = _read_list(args.symbols_file, args.symbols)
    if args.cost_only:
        est = estimate_cost(len(universe), chunk_size=args.chunk_size)
        n_chunks = est["chunks"]
        whole = exchange_cost(len(EXCHANGE_CODES) if args.exchange.upper() == "US" else 1)
        payload = {
            **est,
            "whole_exchange_alternative": {
                "requests": len(EXCHANGE_CODES) if args.exchange.upper() == "US" else 1,
                "api_calls": whole,
                "note": (
                    "a whole-exchange request is a flat 100 calls, so a "
                    "US-wide panel is 400 calls (NASDAQ/NYSE/AMEX/BATS) against "
                    "100 x chunks + N for a symbols list - cheaper for a large "
                    "universe, and it needs the same gated plan"
                ),
            },
        }
        print(json.dumps(payload, indent=2) if args.json else
              f"{est['symbols']} symbol(s) -> {n_chunks} chunk(s), "
              f"{est['api_calls']} API call(s) ({est['model']}); "
              f"whole-exchange alternative: {whole} API call(s)")
        return 0
    if not dates:
        parser.error("--dates or --dates-file is required")
        return 2

    if args.evaluate_only:
        panels = load_panel_series(dates, universe, cache_dir=cache_dir)
        build = None
        if not panels:
            print(f"no cached panel for {dates} under {panel_path(cache_dir, dates[0])}")
    else:
        # The price leg is always present: it carries each name's close, which
        # every forward-return statistic needs. `--no-technical` skips the
        # component assembly, not the closes.
        build = build_panel(
            dates, universe,
            transport=eodhd_bulk_transport(exchange=args.exchange,
                                           chunk_size=args.chunk_size),
            price_provider=PriceProvider(),
            cache_dir=cache_dir, chunk_size=args.chunk_size,
            technical=not args.no_technical,
        )
        panels = load_panel_series(dates, universe, cache_dir=cache_dir)
        panels = {d: panels.get(d, {}) for d in dates}
    report = evaluate_panel(
        panels, dates=dates, holding=args.holding, n_buckets=args.buckets,
        train_frac=args.train_frac, cpcv_splits=args.cpcv_splits,
        embargo=args.embargo, seed=args.seed, n_boot=args.n_boot,
    )

    if args.json:
        print(json.dumps({**report, "build": build}, indent=2, default=str))
    else:
        print(render_text(report, build))
        if build is None:
            print("\n(evaluate-only: no fetch this run; --symbols is a filter over "
                  "the cached rows)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


__all__ = [
    # the panel
    "BulkResult",
    "CHUNK_SIZE",
    "BULK_REQUEST_CALLS",
    "EXCHANGE_CODES",
    "META_KEY",
    "PANELS_DIRNAME",
    "PriceProvider",
    "build_panel",
    "closes_asof",
    "default_cache_dir",
    "eodhd_bulk_transport",
    "estimate_cost",
    "exchange_cost",
    "load_panel_series",
    "panel_path",
    "read_panel",
    "slice_bars",
    "split_chunks",
    "technical_rows_asof",
    "write_panel",
    # the vendor mapping
    "BULK_HIGHLIGHTS",
    "BULK_YEARLY_STATEMENTS",
    "canonical_fin_from_bulk",
    "panel_row_from_bulk",
    "panel_row_from_fin",
    # the engines
    "ENGINE_MODULES",
    "ENGINE_NOT_SCORED",
    "REDUNDANCY_BLOCKS",
    "block_members",
    "block_report",
    "category_findings",
    "engine_registry",
    "engine_weight_vector",
    # the statistics
    "HARNESS_GATE",
    "MIN_PAIRS",
    "OOS_TRAIN_FRAC",
    "REDUNDANT_ABS_CORR",
    "STATUS_ADVISORY",
    "STATUS_RESEARCH_ONLY",
    "evaluate_panel",
    "factor_statistics",
    "multiple_testing",
    "observation_matrix",
    "period_series",
    "redundancy_matrix",
    "render_text",
    "to_prices",
    "to_scores",
    # the CLI
    "main",
]
