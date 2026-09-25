"""Screen cheap US stocks that are down on the day, then keep the highest FundamentalScores.

The screen is the owner's, taken from the broker app's filter panel:

    Market: United States      Mkt cap >= 10B     P/E TTM <= 33
    P/B <= 9                   P/S TTM <= 8       Price-to-Cash-Flow TTM <= 25

plus a same-day move filter (default: down 2% or more), then the engine's
``fundamental_score`` composite over the survivors, keeping score >= 64.

Why this shape - what the vendors can and cannot do (verified 2026-09-24):

* ONE call answers the day filter for the whole US market: EODHD's bulk
  real-time feed (``get_top_movers_symbols_eodhd``, ~18k rows, ``change_p``).
* FOUR of the five valuation criteria are server-side in moomoo's Stock
  Screening V2 (``screen_value_dip_moomoo``: ``pe_max``, ``market_cap_min``,
  ``pb_max``). No vendor in this repo serves P/S or P/CF - EODHD's own screener
  403s on the current plan, Massive's ratios endpoint 403s on the free plan - so
  those two are computed client-side by ``ratios.compute_ratios``, their sole
  producer (``market_cap / revenue``, ``market_cap / operating_cashflow``).
* The scoring pass costs ZERO extra vendor calls. ``fundamental_score(panel)``
  scores a whole cross-section in one pass, and the panel is the run's own
  screened set - the same convention ``scripts/value_screener.py`` uses
  (``resolve_peer_universe(tickers=..., financials=...)`` over the financials
  the screen already fetched).

Two facts about the composite that this tool prints rather than hides, because
they change what the threshold means:

1. ``fundamental_score``'s composite is a **tie-aware percentile x100 over the
   panel it is given**, not an absolute quality grade, and the engine applies
   **no band table** to it (its own ``basis`` says so). "64" therefore means
   "top ~36% of THIS panel". The four sub-scores are the advisory output and DO
   have band tables - they are printed beside the composite.
2. The composite carries ``status=RESEARCH_ONLY``: an unvalidated combination.
   The four sub-scores carry ``status=ADVISORY``. Both are advisory to research;
   neither reaches ``opportunity_score`` and neither may gate a trade.

Usage::

    py -3.12 scripts/value_score_screen.py --roe-min 15 --chg5d-max 3 --rsi-max 55
    py -3.12 scripts/value_score_screen.py                    # panel bounds only
    py -3.12 scripts/value_score_screen.py --offline-demo     # no vendor calls
    py -3.12 scripts/value_score_screen.py --limit 40 --top 20
"""

from __future__ import annotations

import argparse
import contextlib
import logging
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

# Reuse the screener's own plumbing rather than re-implementing it: the
# memoized financials fetch (so the peer-panel pass re-uses exactly what the
# ratio pass fetched), the EODHD exchange cache, the non-equity name gate and
# the timestamped markdown writer.
from scripts.value_screener import (  # noqa: E402
    _CASHFLOW_CACHE,
    _EODHD_EXCH_CACHE,
    _exchange_ok,
    _fetch_fin_cached,
    _is_non_equity,
    save_watchlist,
)
from tradingagents.dataflows.interface import route_to_vendor  # noqa: E402
from tradingagents.dataflows.statement_parsing import _canonicalize  # noqa: E402
from tradingagents.strategies.ratios import compute_ratios  # noqa: E402

logging.basicConfig(level=logging.WARNING)
logger = logging.getLogger("value_score_screen")

# The screen's defaults - the app panel's bounds, verbatim.
DEFAULT_MAX_CHG = -2.0      # percent; keep names at or below this same-day move
DEFAULT_MIN_MCAP = 10e9     # the panel's 10B floor, in USD
DEFAULT_PE_MAX = 33.0
DEFAULT_PB_MAX = 9.0
DEFAULT_PS_MAX = 8.0
DEFAULT_PCF_MAX = 25.0
DEFAULT_SCORE_MIN = 64.0

# The composite has no band table; these are the nearest PUBLISHED edges in the
# sub-score band tables, printed so a reader can see 64 does not sit on one.
NEAREST_PUBLISHED_EDGES = (60.0, 65.0)

#: Vendor calls this run made, by stage - printed in the footer.
_CALLS: dict[str, int] = {}


def _bump(stage: str, n: int = 1) -> None:
    _CALLS[stage] = _CALLS.get(stage, 0) + n


def _f(v) -> float | None:
    """Float a vendor value; None when absent / unparseable / non-finite."""
    try:
        out = float(v)
    except (TypeError, ValueError):
        return None
    return out if out == out and out not in (float("inf"), float("-inf")) else None


def _fmt(v, nd: int = 2) -> str:
    x = _f(v)
    return "n/a" if x is None else f"{x:,.{nd}f}"


# --------------------------------------------------------------------------
# Stage 0 - the day filter, whole US market, ONE call (EODHD bulk feed)
# --------------------------------------------------------------------------


def stage_decliners(args) -> tuple[dict, set]:
    """``{symbol: change_pct}`` for common stocks down ``--max-chg`` or more.

    One EODHD bulk call + one cached symbol-list call. The bulk feed carries no
    name/type field, so warrants/units/ETFs dominate a raw decliner list; the
    symbol list's ``Type == "Common Stock"`` set and its ``Exchange`` column do
    the equity and NYSE/Nasdaq gates here, which also spares the moomoo screen
    its per-row ``get_stock_basicinfo`` exchange check.
    """
    from tradingagents.dataflows.eodhd import (
        NoMarketDataError,
        VendorRateLimitError,
        get_exchange_symbols_eodhd,
        get_top_movers_symbols_eodhd,
    )

    want = max(args.limit * 40, 4000)
    movers = get_top_movers_symbols_eodhd(
        direction="losers", count=want, min_price=args.min_price
    )
    _bump("eodhd bulk real-time feed")
    down = {
        m["symbol"]: _f(m.get("change_p"))
        for m in movers
        if m.get("symbol") and (_f(m.get("change_p")) or 0.0) <= args.max_chg
    }
    logger.info("day filter: %d of %d feed rows at or below %.1f%%",
                len(down), len(movers), args.max_chg)
    if not down:
        raise NoMarketDataError("US", "US", detail="no decliners in the bulk feed")

    common: set = set()
    allowed = {e.strip().upper() for e in str(args.exchanges or "").split(",") if e.strip()}
    try:
        syms = get_exchange_symbols_eodhd("US")
        _bump("eodhd symbol list (cached)")
        common = {
            str(s.get("Code")).upper()
            for s in syms
            if str(s.get("Type") or "") == "Common Stock" and s.get("Code")
        }
        if allowed:
            _EODHD_EXCH_CACHE.update({
                str(s.get("Code")).upper(): str(s.get("Exchange") or "").upper()
                for s in syms if s.get("Code")
            })
    except (NoMarketDataError, VendorRateLimitError, OSError, ValueError) as exc:
        logger.warning("symbol-list equity filter unavailable (%s); keeping the feed", exc)

    kept = {}
    for sym, chg in down.items():
        if common and sym not in common:
            continue
        if allowed and not _exchange_ok(sym, allowed):
            continue
        kept[sym] = chg
    logger.info("day filter: %d common stocks on %s remain", len(kept),
                "+".join(sorted(allowed)) or "any exchange")
    return kept, common


# --------------------------------------------------------------------------
# Stage 1 - the four server-side valuation criteria, ONE paginated screen
# --------------------------------------------------------------------------


def stage_value_screen(args, universe: set) -> list:
    """Rows from moomoo Screening V2 meeting mcap/P-E/P-B, intersected with Stage 0.

    ``roe_min`` / ``chg5d_max`` / ``rsi_max`` are the owner's extra anchors. The
    API takes ROE and the 5-day change as decimal fractions and RSI on its 0-100
    scale, so the CLI takes the first two in percent and converts here; ``0``
    disables any of the three. ``exchanges`` is deliberately NOT passed to the
    screen: Stage 0's EODHD symbol list already gates NYSE/Nasdaq for one cached
    call, where the screen's own gate costs one ``get_stock_basicinfo`` per row.
    """
    from tradingagents.dataflows.moomoo import (
        MoomooNotConfiguredError,
        close_context,
        screen_value_dip_moomoo,
    )

    try:
        rows = screen_value_dip_moomoo(
            market="US",
            pe_min=0.0,
            pe_max=args.pe_max,
            market_cap_min=args.min_mcap,
            roe_min=args.roe_min / 100.0 if args.roe_min else None,
            net_margin_min=None,
            debt_assets_max=None,
            chg5d_max=args.chg5d_max / 100.0 if args.chg5d_max else None,
            rsi_max=args.rsi_max or None,
            price_min=args.min_price or None,
            pb_min=None,
            pb_max=args.pb_max,
            dip_days=5,
            exchanges=None,        # Stage 0's EODHD list gates exchange, for free
            page_count=200,
            max_pages=max(1, -(-args.limit * 8 // 200)),
        )
    except MoomooNotConfiguredError as exc:
        raise SystemExit(f"moomoo screen unavailable: {exc}") from exc
    finally:
        with contextlib.suppress(Exception):
            close_context()
    _bump("moomoo screen V2 (paginated)")

    out, seen = [], set()
    for row in rows:
        if _is_non_equity(row.get("name")):
            continue
        sym = str(row.get("symbol") or "").upper()
        if not sym or sym in seen or sym not in universe:
            continue
        seen.add(sym)
        row["symbol"] = sym
        out.append(row)
    logger.info("value screen: %d rows meet mcap>=%.0fB, 0<P/E<=%.0f, P/B<=%.0f "
                "and are down on the day", len(out), args.min_mcap / 1e9,
                args.pe_max, args.pb_max)
    return out


# --------------------------------------------------------------------------
# Stage 2 - P/S and P/CF, the two ratios no vendor here serves
# --------------------------------------------------------------------------


def stage_ratios(args, rows: list, change: dict) -> tuple[list, dict, dict]:
    """Apply P/S and P/CF client-side; keep the financials for the scoring pass.

    ``compute_ratios`` never fabricates: a ratio whose input is missing comes
    back ``None``, and a ``None`` bound fails CLOSED here (the name is dropped
    and counted), never treated as a pass.
    """
    kept, fin_by_ticker, fails = [], {}, {"ps": 0, "pcf": 0, "pe": 0, "pb": 0, "no_fin": 0}
    for row in rows[: args.limit]:
        sym = row["symbol"]
        try:
            fin = _fetch_fin_cached(sym, args.date)
        except Exception as exc:  # noqa: BLE001 - one name never aborts the screen
            logger.info("skip %s: financials unavailable (%s)", sym, exc)
            fails["no_fin"] += 1
            continue
        if not isinstance(fin, dict):
            fails["no_fin"] += 1
            continue
        _bump("per-name financials")

        # P/CF needs the cash-flow statement, and fetch_ticker does not pull one
        # (its payloads are fundamentals, balance sheet and income statement), so
        # the canonical items arrive without operating_cashflow and P/CF is
        # uncomputable for EVERY name. One annual cash-flow fetch per name, cached
        # for the run and parsed by the engine's own canonicalizer, supplies it; a
        # name whose OCF stays missing then fails the P/CF gate below rather than
        # passing unscored.
        if (_f(fin.get("operating_cashflow")) is None
                and _f(fin.get("operating_cashflow_ttm")) is None):
            _bump("per-name cash-flow statement")
            try:
                cf_key = (sym.upper(), args.date)
                if cf_key not in _CASHFLOW_CACHE:
                    _CASHFLOW_CACHE[cf_key] = route_to_vendor(
                        "get_cashflow", sym, "annual", args.date
                    )
                canonical = _canonicalize(_CASHFLOW_CACHE.get(cf_key) or "")
                ocf = _f((canonical or {}).get("operating_cashflow"))
                if ocf is not None:
                    fin["operating_cashflow"] = ocf
            except Exception as exc:  # noqa: BLE001 - a missing leg is a gate failure
                logger.info("cash-flow leg unavailable for %s: %s", sym, exc)

        # Every FETCHED name enters the panel, not only those that pass the ratio
        # gates: the composite is a cross-sectional percentile and the engine
        # refuses a peer set below its own floor, so the panel is the whole
        # fetched cross-section and the survivors are READ OUT of it.
        fin_by_ticker[sym] = fin

        caps = compute_ratios(fin, price=_f(row.get("price")))
        ps, pcf = _f(caps.get("price_to_sales")), _f(caps.get("price_to_cash_flow"))
        if ps is None or ps > args.ps_max:
            fails["ps"] += 1
            logger.info("skip %s: P/S %s", sym, _fmt(ps))
            continue
        if pcf is None or pcf > args.pcf_max:
            fails["pcf"] += 1
            logger.info("skip %s: P/CF %s", sym, _fmt(pcf))
            continue
        # The client is authoritative for the whole screen, not only P/S and
        # P/CF: a name the server screen let through is re-checked here, and a
        # ratio that cannot be computed fails CLOSED rather than passing.
        pe, pb = _f(caps.get("price_to_earnings")), _f(caps.get("price_to_book"))
        if pe is None or not (0.0 < pe <= args.pe_max):
            fails["pe"] += 1
            logger.info("skip %s: P/E %s", sym, _fmt(pe))
            continue
        if pb is None or pb > args.pb_max:
            fails["pb"] += 1
            logger.info("skip %s: P/B %s", sym, _fmt(pb))
            continue
        # Client-side market-cap cross-check (the repo's "client is
        # authoritative" rule): drop only when a cap IS present and below the
        # floor - an unparsed cap is not evidence of a small company.
        cap = _f(caps.get("market_cap"))
        if cap is not None and cap < args.min_mcap:
            logger.info("skip %s: market cap %.2fB < floor", sym, cap / 1e9)
            continue
        row["ratios"] = caps
        row["change_p"] = change.get(sym)
        kept.append(row)
    logger.info("client ratios: %d names pass P/E<=%.0f, P/B<=%.0f, P/S<=%.0f, "
                "P/CF<=%.0f (dropped: %d on P/E, %d on P/B, %d on P/S, %d on "
                "P/CF, %d unfetchable)", len(kept), args.pe_max, args.pb_max,
                args.ps_max, args.pcf_max, fails["pe"], fails["pb"],
                fails["ps"], fails["pcf"], fails["no_fin"])
    return kept, fin_by_ticker, fails


# --------------------------------------------------------------------------
# Stage 3 - the composite, over a panel the run already paid for
# --------------------------------------------------------------------------


def stage_score(args, fin_by_ticker: dict) -> tuple[dict, dict, str, dict, str]:
    """``({name: score}, {name: withheld reason}, basis, subscores, panel_note)``.

    Two panel sources, in order of preference.

    ``--panel <date>`` reads the BUILT panel for that date
    (``data_cache_dir/panels/<date>.json``, one file per date, never re-fetched)
    and scores the whole of it, so the percentile is relative to that panel -
    the market-relative reading the plan's §6 exists for. A candidate the panel
    does not carry (a non-US filer, a pre-XBRL filer, a 20-F whose market cap was
    withheld) is refused BY NAME, never scored as 0.

    Without ``--panel`` the panel is this run's own fetched cross-section, which
    must be WIDER than the survivors: ``factors.category_scores`` refuses a peer
    set below its ``min_peers`` floor, and it costs no vendor calls because every
    name in it was already fetched. A missing or empty panel FILE falls back to
    that cross-section and says so in the report rather than silently changing
    the denominator.
    """
    from tradingagents.strategies.fundamental_score import fundamental_score
    from tradingagents.strategies.peer_universe import resolve_peer_universe

    panel: dict = {}
    note = ""
    if getattr(args, "panel", None):
        from scripts.score_panel import load_panel_series

        loaded = load_panel_series([args.panel], None) or {}
        panel = {str(k).upper(): dict(v)
                 for k, v in (loaded.get(args.panel) or {}).items()
                 if isinstance(v, dict)}
        if panel:
            note = f"{len(panel)} names from the built panel for {args.panel}"
        else:
            note = (f"NO built panel for {args.panel} - fell back to this run's "
                    f"fetched cross-section")
            logger.warning("no panel file for %s; falling back to the run's "
                           "cross-section", args.panel)
    if not panel:
        names = sorted(fin_by_ticker)
        if len(names) < 2:
            logger.warning("fewer than 2 names survived; the composite is a "
                           "cross-sectional read and cannot be computed")
            return ({}, dict.fromkeys(names, "cross-section too small (needs >= 2 names)"),
                    "", {}, note or "this run's fetched cross-section (too small)")
        panel_res = resolve_peer_universe(
            tickers=names,
            financials=fin_by_ticker,
            current_date=args.date,
            include_score_metrics=True,
        )
        _bump("peer-universe build (0 extra vendor calls: financials reused)")
        panel = {str(k).upper(): dict(v) for k, v in (panel_res.get("metrics") or {}).items()}
        note = note or f"{len(panel)} names from this run's fetched cross-section"
    scored = fundamental_score(panel)
    withheld = dict(scored.get("withheld") or {})
    # The engine refuses a peer set below its floor and says why at the SUB-SCORE
    # level ("peer set below the floor (5 < 8 names)"), which the composite's own
    # message does not repeat. Every unscored candidate carries that reason, so a
    # refusal is never rendered as "no reason recorded".
    reasons = sorted({
        str(res.get("unavailable"))
        for res in (scored.get("subscores") or {}).values()
        if isinstance(res, dict) and res.get("unavailable")
    })
    if reasons or scored.get("unavailable"):
        why = "; ".join(reasons) or str(scored.get("unavailable"))
        for name in sorted(panel):
            withheld.setdefault(name, why)
    # A candidate the panel does not carry is refused BY NAME - the honest gap
    # the SEC leg records (no 10-K/20-F/40-F filed, or a withheld 20-F market cap).
    for name in sorted(fin_by_ticker):
        if name not in panel and name not in scored.get("scores", {}):
            withheld.setdefault(
                name, f"not in the panel ({args.panel or 'run cross-section'})"
            )
    return (
        dict(scored.get("scores") or {}),
        withheld,
        str(scored.get("basis") or ""),
        dict(scored.get("subscores") or {}),
        note,
    )


# --------------------------------------------------------------------------
# Rendering
# --------------------------------------------------------------------------

_HEAD = (
    "ticker", "1d%", "mcap$B", "P/E", "P/B", "P/S", "P/CF",
    "FQS", "VS", "FRS", "FGS", "score",
)


def _sub_cell(subs: dict, sub: str, name: str) -> str:
    res = subs.get(sub) or {}
    val = (res.get("scores") or {}).get(name)
    if val is None:
        return "n/a"
    band = (res.get("bands") or {}).get(name) or ""
    return f"{_f(val):.0f} {band}".strip()


def _row_cells(row: dict, scores: dict, subs: dict) -> list:
    """One table row: the screen's own columns, then the engine's reads."""
    sym = row["symbol"]
    caps = row.get("ratios") or {}
    score = scores.get(sym)
    return [
        sym,
        _fmt(row.get("change_p"), 2),
        _fmt((_f(caps.get("market_cap")) or 0) / 1e9 or None, 1),
        _fmt(caps.get("price_to_earnings")),
        _fmt(caps.get("price_to_book")),
        _fmt(caps.get("price_to_sales")),
        _fmt(caps.get("price_to_cash_flow")),
        _sub_cell(subs, "FQS", sym),
        _sub_cell(subs, "VS", sym),
        _sub_cell(subs, "FRS", sym),
        _sub_cell(subs, "FGS", sym),
        "withheld" if score is None else f"{_f(score):.2f}",
    ]


def render(kept: list, scores: dict, withheld: dict, subs: dict,
           args, basis: str, panel_note: str = "") -> str:
    """The markdown report: the screen's own columns, then the engine's reads."""
    rows = sorted(kept, key=lambda r: -(scores.get(r["symbol"]) or -1.0))
    # These counts are over the CANDIDATES. The panel is wider than they are -
    # every name stage 2 fetched enters it - so scores.values() is the panel's
    # size, not this list's, and counting over it inverted the header.
    scored_n = len([r for r in rows if scores.get(r["symbol"]) is not None])
    miss = [r for r in rows if scores.get(r["symbol"]) is None]
    qual = [r for r in rows if scores.get(r["symbol"]) is not None
            and scores[r["symbol"]] >= args.score_min]
    below = [r for r in rows if scores.get(r["symbol"]) is not None
             and scores[r["symbol"]] < args.score_min]
    panel_n = len([s for s in scores.values() if s is not None])
    lines = [
        f"# Value screen: candidates clearing FundamentalScore >= {args.score_min:g}",
        "",
        f"- Run: {datetime.now():%Y-%m-%d %H:%M} · date {args.date} · "
        f"universe: {args.exchanges or 'any'} common stocks",
        f"- Screen: mcap >= ${args.min_mcap / 1e9:.0f}B · 0 < P/E TTM <= "
        f"{args.pe_max:g} · P/B <= {args.pb_max:g} · P/S TTM <= {args.ps_max:g} · "
        f"P/CF TTM <= {args.pcf_max:g} · same-day move <= {args.max_chg:g}%"
        + (f" · ROE >= {args.roe_min:g}%" if args.roe_min else "")
        + (f" · 5-day change <= {args.chg5d_max:g}%" if args.chg5d_max else "")
        + (f" · RSI(14) <= {args.rsi_max:g}" if args.rsi_max else ""),
        f"- Panel: {panel_note}",
        f"- Scoring pass: {scored_n} of {len(rows)} candidates scored, {panel_n} "
        f"panel name(s) carrying a composite, {len(miss)} withheld, "
        f"{len(qual)} clear the {args.score_min:g} cut",
        *(["- Candidate set: the deepest decliners with --no-moomoo, so this is "
           "a PARTIAL scan - the server-side screen needs OpenD and was skipped."]
          if args.no_moomoo else []),
        "",
        "**The `score` column is `RESEARCH_ONLY`** - a tie-aware percentile x100 "
        "over the panel named above, with no band table "
        f"(nearest published sub-score edges: {NEAREST_PUBLISHED_EDGES[0]:g} and "
        f"{NEAREST_PUBLISHED_EDGES[1]:g}). The four sub-score columns are the "
        "`ADVISORY` output that does carry band tables. Neither the composite "
        "nor the sub-scores reaches `opportunity_score`, and neither may gate a "
        "trade.",
        "",
        f"### Clear the {args.score_min:g} cut",
        "| " + " | ".join(_HEAD) + " |",
        "| " + " | ".join("---" for _ in _HEAD) + " |",
    ]
    for row in qual:
        lines.append("| " + " | ".join(_row_cells(row, scores, subs)) + " |")
    if not qual:
        # The cut is the owner's criterion, so an empty result must say so and
        # name the best few rather than printing an empty table in silence.
        best = ", ".join(f"{r['symbol']} {scores[r['symbol']]:.2f}" for r in below[:3])
        lines += ["", f"**None of the {len(rows)} scored candidate(s) cleared "
                  f"{args.score_min:g}.**"
                  + (f" Highest: {best}." if best else "")
                  + (f" {len(miss)} withheld." if miss else "")
                  + " Re-run with --show-excluded to list them."]
    if below and args.show_excluded:
        lines += ["", f"### Scored, below the {args.score_min:g} cut", "",
                  "| " + " | ".join(_HEAD) + " |",
                  "| " + " | ".join("---" for _ in _HEAD) + " |"]
        for row in below:
            lines.append("| " + " | ".join(_row_cells(row, scores, subs)) + " |")
    if miss and args.show_excluded:
        lines += ["", "### Withheld - no composite", "",
                  "| ticker | reason |", "| --- | --- |"]
        for row in miss:
            lines.append(f"| {row['symbol']} | "
                         f"{withheld.get(row['symbol'], 'no reason recorded')} |")
    if basis:
        lines += ["", f"`basis` (the engine's own words): {basis}"]
    lines += [
        "",
        "## What this list is and is not",
        "",
        "- **Not a signal.** Both score layers are advisory to research; the "
        "executor's `opportunity_score` stays null by decision (Q1, "
        "`docs/scores/FundamentalScore.md`).",
        "- **Selection overlap, disclosed.** The screen filters on four "
        "valuation factors (P/E, P/B, P/S, P/CF) that the composite also "
        "includes, so a surviving name is pre-selected on part of what the "
        "composite then ranks. Read the sub-score columns, not only the "
        "composite.",
        "- **Panel dependence.** The percentile is relative to the panel named "
        "above, not to the market as a whole: a different panel changes every "
        "score.",
        "- **Liquidity/execution are not checked here.** Nothing in this list "
        "has been reviewed for spread, depth or a session window; the "
        "pre-market and risk gates are separate reads.",
        "",
        "### Vendor calls this run",
        "",
    ]
    lines += [f"- {stage}: {n}" for stage, n in _CALLS.items()]
    lines += [f"- total: {sum(_CALLS.values())}", ""]
    return "\n".join(lines)


# --------------------------------------------------------------------------
# Offline demo - the scoring and threshold half, with zero vendor calls
# --------------------------------------------------------------------------


def offline_demo(args) -> int:
    """Prove stages 3-5 on a fixture panel: no network, deterministic.

    The panel is the test suite's rising cross-section
    (``tests/test_fundamental_score.py::_panel``), so the composite, the
    sub-score bands, the withholding path and the >= threshold filter are all
    exercised without touching a vendor.
    """
    from tradingagents.strategies.fundamental_score import fundamental_score

    n = 40
    panel = {}
    for i in range(n):
        # The test fixture's exact key set (FQS's six + VS's three), so the
        # composite is recomputable from the sub-scores as the suite expects.
        panel[f"N{i:02d}"] = {
            "f": float(i),
            "m": float(n - i),
            "gp_a": 0.30 + i / 100.0,
            "noa": 0.10 * i,
            "accruals": -0.02 * i,
            "return_on_equity": 0.05 + i / 100.0,
            "ev_ebit": 30.0 - i,
            "price_to_earnings": 40.0 - 2 * i,
            "earnings_yield": 0.02 + i / 200.0,
        }
    scored = fundamental_score(panel)
    scores = {k: v for k, v in (scored.get("scores") or {}).items() if v is not None}
    kept = sorted(scores.items(), key=lambda kv: -kv[1])
    print(f"offline demo: {len(panel)} synthetic names, {len(kept)} scored, "
          f"{(scored.get('withheld') or {}) and len(scored['withheld']) or 0} withheld")
    print(f"status: {scored.get('status')}")
    print(f"keeping score >= {args.score_min:g}: "
          f"{sum(1 for _, v in kept if v >= args.score_min)} names")
    print()
    print("rank  name   score   FQS(band)          VS(band)")
    subs = scored.get("subscores") or {}
    for i, (name, val) in enumerate(kept, 1):
        if i > args.top:
            break
        fqs = _sub_cell(subs, "FQS", name)
        vs = _sub_cell(subs, "VS", name)
        print(f"{i:>4}  {name:<6} {val:6.2f}  {fqs:<18} {vs}")
    print()
    print(f"basis: {scored.get('basis')}")
    print("\nno vendor calls were made in this mode.")
    return 0


# --------------------------------------------------------------------------


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("-d", "--date", default=datetime.now().strftime("%Y-%m-%d"),
                        help="analysis date (default: today)")
    parser.add_argument("--max-chg", type=float, default=DEFAULT_MAX_CHG,
                        help=f"keep names at or below this same-day %% move "
                             f"(default {DEFAULT_MAX_CHG:g}; 0 disables)")
    parser.add_argument("--min-mcap", type=float, default=DEFAULT_MIN_MCAP,
                        help="market-cap floor in USD (default 10B)")
    parser.add_argument("--pe-max", type=float, default=DEFAULT_PE_MAX,
                        help=f"max P/E TTM (default {DEFAULT_PE_MAX:g})")
    parser.add_argument("--pb-max", type=float, default=DEFAULT_PB_MAX,
                        help=f"max P/B (default {DEFAULT_PB_MAX:g})")
    parser.add_argument("--ps-max", type=float, default=DEFAULT_PS_MAX,
                        help=f"max P/S TTM (default {DEFAULT_PS_MAX:g})")
    parser.add_argument("--pcf-max", type=float, default=DEFAULT_PCF_MAX,
                        help=f"max Price-to-Cash-Flow TTM (default {DEFAULT_PCF_MAX:g})")
    parser.add_argument("--roe-min", type=float, default=0.0,
                        help="ROE floor in percent (0 disables)")
    parser.add_argument("--chg5d-max", type=float, default=0.0,
                        help="max 5-day change in percent (0 disables; 3 = no "
                             "more than +3%% over the last 5 days)")
    parser.add_argument("--rsi-max", type=float, default=0.0,
                        help="max RSI(14) on its 0-100 scale (0 disables)")
    parser.add_argument("--score-min", type=float, default=DEFAULT_SCORE_MIN,
                        help=f"keep composite >= this (default {DEFAULT_SCORE_MIN:g}; "
                             "the composite has no band table, so this is a "
                             "research cut, not an engine boundary)")
    parser.add_argument("--limit", type=int, default=60,
                        help="max names to fetch financials for (default 60)")
    parser.add_argument("--top", type=int, default=40, help="rows to render (default 40)")
    parser.add_argument("--min-price", type=float, default=15.0,
                        help="price floor for the bulk feed and the screen (default 15)")
    parser.add_argument("--exchanges", type=str, default="NYSE,NASDAQ",
                        help="listing exchanges to keep ('' disables)")
    parser.add_argument("--out-dir", default="screener",
                        help="folder for the saved markdown (default 'screener')")
    parser.add_argument("--panel", default=None, metavar="DATE",
                        help="score against the BUILT panel for DATE "
                             "(data_cache_dir/panels/<DATE>.json): the whole panel "
                             "is the peer set, so the percentile is relative to it "
                             "rather than to this run's screened names. Falls back "
                             "to the run's cross-section, labelled, if no file exists")
    parser.add_argument("--show-excluded", action="store_true",
                        help="also list candidates scored below the cut and every "
                             "withheld name (default: qualifying names only)")
    parser.add_argument("--no-moomoo", action="store_true",
                        help="skip the server-side screen (needs no OpenD); the "
                             "candidate set becomes the deepest --limit decliners "
                             "and every ratio is gated client-side")
    parser.add_argument("--no-save", action="store_true", help="print only, write nothing")
    parser.add_argument("--offline-demo", action="store_true",
                        help="run the scoring/threshold half on a synthetic panel; "
                             "no vendor calls")
    args = parser.parse_args(argv)

    if args.offline_demo:
        return offline_demo(args)

    change, _ = stage_decliners(args)
    if args.no_moomoo:
        # The feed is sorted deepest-decliner-first, so the cap keeps the
        # sharpest same-day moves. This is a PARTIAL scan and the report says so.
        deepest = list(change)[: args.limit]
        print(f"[--no-moomoo] server screen skipped; taking the {len(deepest)} "
              f"deepest decliners as the candidate set.")
        rows = [{"symbol": s, "change_p": change.get(s)} for s in deepest]
    else:
        rows = stage_value_screen(args, set(change))
    if not rows:
        print("no candidates: nothing met both the day filter and the screen.")
        return 0
    kept, fin_by_ticker, fails = stage_ratios(args, rows, change)
    print(f"[funnel] decliners {len(change)} -> candidates {len(rows)} -> "
          f"passed the ratio gates {len(kept)} (dropped: {fails['pe']} on P/E, "
          f"{fails['pb']} on P/B, {fails['ps']} on P/S, {fails['pcf']} on P/CF, "
          f"{fails['no_fin']} unfetchable)")
    if not kept:
        print("no candidates survived the ratio gates. Two usual causes: the "
              "candidate set is size-biased (the deepest decliners are small "
              "caps - the server-side screen exists to prevent exactly that), "
              "or a ratio could not be computed at all, which fails closed. "
              "Raise --limit, or run with OpenD up for the full screen.")
        return 0
    scores, withheld, basis, subs, panel_note = stage_score(args, fin_by_ticker)
    if kept and not any(s is not None for s in scores.values()):
        print(f"[score] the engine produced NO composite for {len(kept)} "
              f"candidate(s) over a {len(fin_by_ticker)}-name panel; the "
              f"per-name reason is in the report's Withheld table. A "
              f"cross-sectional percentile is not computed over a handful of "
              f"names, so a peer set below the floor yields nothing rather than "
              f"noise (factors.category_scores, min_peers=8).")
    report = render(kept, scores, withheld, subs, args, basis, panel_note)
    print(report)
    if not args.no_save:
        try:
            path = save_watchlist(report, args.out_dir)
            print(f"\n[saved] {path}")
        except OSError as exc:
            print(f"\n[save failed] {exc}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
