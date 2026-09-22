"""Peer-universe resolver for the round-3 cross-sectional scores (S3 / S10).

One resolver returns the metrics panel, the sector labels and the peer count
that the G/C-Score industry medians and the composite quality score both read,
so those consumers cannot drift from the screener's own scan universe. Metrics
come from ``statement_parsing.screen_ticker`` (the same function the value
screener calls per row) for F / M / Z / GP-A / NOA, plus ``normalized`` for O
and the Sloan accruals ratio.

Import-safe (no network at import) and never raises: a per-name failure is
counted in ``dropped`` and skipped. Bounded parallelism via a thread pool.

The caller may supply the universe it already scanned (``tickers=``) and its
per-name canonical financials (``financials=``) so no statement is fetched
twice; when both are given the EODHD symbol-list fetch is skipped entirely.
"""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed

_NYSE_NASDAQ = ("NYSE", "NASDAQ")


def _latest(v):
    """Current-period value of a canonical item (flat float or current/prior dict)."""
    if isinstance(v, dict):
        return v.get("current", v.get("value"))
    return v


def _prior(v):
    """Prior-period value of a canonical item (dict with a ``prior`` key)."""
    return v.get("prior") if isinstance(v, dict) else None


def _fnum(v):
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


# The metric keys the score engine's sub-scores read that the round-3 quality
# panel does not carry. Opt-in (`include_score_metrics`), because adding them to
# the default panel would change the quality composite's own `coverage["of"]`
# and its droplist - a published row that must stay byte-identical.
SCORE_METRIC_RATIO_KEYS: tuple[str, ...] = (
    "ev_ebitda",
    "ev_ebit",
    "ev_sales",
    "price_to_earnings",
    "price_to_book",
    "price_to_sales",
    "price_to_cash_flow",
    "price_to_free_cash_flow",
    "return_on_equity",
    "return_on_assets",
    "debt_to_equity",
    "current",
    "quick",
)

SCORE_METRIC_SCREEN_KEYS: tuple[str, ...] = (
    "earnings_yield",
    "eps_yoy",
    "revenue_yoy",
)


def _panel_from_fin(ticker: str, fin: dict, *, include_score_metrics: bool = False) -> dict:
    """The canonical metric panel for one name, from an already-fetched ``fin``.

    F / M / Z / GP-A / NOA come from ``screen_ticker`` (values as it returns
    them); O and the accruals ratio from ``strategies.normalized`` (there is no
    ``screen_ticker`` output for those). A metric that is unavailable for the
    name is simply absent from its dict. ``capex_quality`` is not computed here
    because it needs the annual series the single statement fetch does not
    carry.

    ``include_score_metrics`` adds the factors the `FundamentalScore` sub-scores
    consume and the quality panel does not carry - the valuation/profitability
    ratio block (`strategies/ratios.compute_ratios`, the one producer of those
    keys), ``screen_ticker``'s own earnings yield and growth legs, and the
    Zmijewski X. It is **opt-in** because the quality composite's published
    coverage and droplist are computed over the panel's key set: adding keys to
    the default panel would change a row that must not move.
    """
    from tradingagents.dataflows.statement_parsing import screen_ticker
    from tradingagents.strategies.normalized import accruals_ratio, ohlson_o_score

    row = screen_ticker(ticker, fin)
    out: dict = {}
    for src, dst in (
        ("f_score", "f"),
        ("beneish_m", "m"),
        ("altman_z", "z"),
        ("gp_a", "gp_a"),
        ("noa", "noa"),
    ):
        v = row.get(src)
        if v is not None:
            out[dst] = v

    ni = _fnum(_latest(fin.get("net_income")))
    cfo = _fnum(_latest(fin.get("operating_cashflow")))
    ta = _fnum(_latest(fin.get("total_assets")))
    ca = _fnum(_latest(fin.get("current_assets")))
    cl = _fnum(_latest(fin.get("current_liabilities")))
    tl = _fnum(_latest(fin.get("total_liabilities")))
    acc = accruals_ratio(ni, cfo, ta)
    if acc is not None:
        out["accruals"] = acc

    if include_score_metrics:
        # `screen_ticker` runs `enrich_screen_ratios(fin)` first, so `fin` is
        # already the enriched dict the ratio block expects.
        from tradingagents.strategies.normalized import zmijewski_score
        from tradingagents.strategies.ratios import compute_ratios

        for key in SCORE_METRIC_SCREEN_KEYS:
            v = row.get(key)
            if v is not None:
                out[key] = v
        ratios = compute_ratios(fin)
        for key in SCORE_METRIC_RATIO_KEYS:
            v = ratios.get(key)
            if v is not None:
                out[key] = v
        zx = zmijewski_score(ni, ta, tl, ca, cl).get("score")
        if zx is not None:
            out["zmijewski_x"] = zx

    o = ohlson_o_score(
        total_assets=ta,
        total_liabilities=tl,
        working_capital=_fnum(_latest(fin.get("working_capital"))),
        current_assets=ca,
        current_liabilities=cl,
        net_income=ni,
        funds_from_ops=cfo,
        ni_prev=_fnum(_prior(fin.get("net_income"))),
        total_assets_prev=_fnum(_prior(fin.get("total_assets"))),
    )
    if o.get("score") is not None:
        out["o"] = o["score"]
    return out


def resolved_peer_names(ticker: str, *, limit: int = 8) -> list[str]:
    """``[ticker] + its vendor peers[:limit]`` - the tool-level peer set.

    One implementation for every leaf that scores against a peer set
    (`get_composite_rank`, `get_fundamental_score`): the vendor returns a
    rendered ``"Peers: A, B, ..."`` string, which is why this parses it through
    ``peer_symbols`` rather than iterating it (iterating gave the peer set the
    sentence's characters). Never raises: a peer fetch that fails leaves the
    ticker alone, and the caller's peer floor then reports the reason.
    """
    key = str(ticker or "").strip().upper()
    if not key:
        return []
    try:
        from tradingagents.dataflows.finnhub import get_company_peers_finnhub, peer_symbols

        peer_list = [
            p for p in peer_symbols(get_company_peers_finnhub(key)) if p and p != key
        ]
    except Exception:  # noqa: BLE001 - a peer fetch must never break a scoring leaf
        peer_list = []
    return [key] + peer_list[: int(limit)]


def resolve_peer_universe(
    *,
    universe: str = "eodhd-us",
    current_date: str = "",
    max_names: int | None = None,
    workers: int = 4,
    require_nyse_nasdaq: bool = True,
    tickers: list[str] | None = None,
    financials: dict[str, dict] | None = None,
    include_score_metrics: bool = False,
) -> dict:
    """Resolve the peer universe to a metrics panel + sector labels.

    Args:
        universe: label recorded in the basis (default ``eodhd-us``).
        current_date: date passed to the statement fetch.
        max_names: cap on the resolved universe when it is symbol-list sourced.
        workers: bounded thread-pool size (default 4).
        require_nyse_nasdaq: keep only NYSE/Nasdaq names from the symbol list.
        tickers: when given, THIS is the universe - the EODHD symbol-list fetch
            is skipped entirely (no exchange filter, no ``max_names`` cap) and
            metrics/sectors are resolved for exactly these names.
        include_score_metrics: add the ratio / earnings-yield / growth / Zmijewski
            factors the `FundamentalScore` sub-scores consume. Default ``False``:
            the round-3 quality composite's coverage and droplist are computed
            over the panel's key set, so its published row must not move.
        financials: ``{ticker: canonical fin}`` already fetched by the caller;
            those names skip the statement fetch and only run ``screen_ticker``.

    Returns:
        ``{"tickers": [...], "n": int, "metrics": {ticker: {metric: value}},
        "sectors": {ticker: label}, "dropped": {reason: count}, "basis": str}``.
    """
    from tradingagents.dataflows.statement_parsing import fetch_ticker
    from tradingagents.dataflows.yfinance_sector import fetch_sector

    fin_cache = {str(k).upper(): v for k, v in (financials or {}).items()}
    dropped: dict = {}

    def _drop(reason: str) -> None:
        dropped[reason] = dropped.get(reason, 0) + 1

    if tickers is not None:
        names: list[str] = []
        seen: set[str] = set()
        for t in tickers:
            code = str(t or "").strip().upper()
            if code and code not in seen:
                seen.add(code)
                names.append(code)
        source = f"explicit ticker list ({len(names)} names)"
    else:
        from tradingagents.dataflows.eodhd import get_exchange_symbols_eodhd

        symbols = get_exchange_symbols_eodhd("US")
        names = []
        seen = set()
        for s in symbols:
            if str(s.get("Type") or "") != "Common Stock":
                continue
            code = str(s.get("Code") or "").strip().upper()
            if not code:
                continue
            exchange = str(s.get("Exchange") or "").strip().upper()
            if require_nyse_nasdaq and exchange not in _NYSE_NASDAQ:
                _drop("exchange filtered (not NYSE/Nasdaq)")
                continue
            if code in seen:
                continue
            seen.add(code)
            names.append(code)
        if max_names is not None:
            names = names[:max_names]
        source = f"EODHD US common stock list ({len(names)} names)"

    def _work(name: str):
        fin = fin_cache.get(name)
        if fin is None:
            try:
                fin = fetch_ticker(name, current_date)
            except Exception:  # noqa: BLE001 - per-name failure, never raised
                return name, None, None, "statement_fetch_failed"
        if not fin:
            return name, None, None, "no_statement"
        try:
            panel = _panel_from_fin(
                name, fin, include_score_metrics=include_score_metrics
            )
        except Exception:  # noqa: BLE001
            return name, None, None, "panel_error"
        if not panel:
            return name, None, None, "no_metrics"
        try:
            sector = fetch_sector(name)
        except Exception:  # noqa: BLE001
            sector = None
        if not sector:
            return name, panel, None, "sector_unavailable"
        return name, panel, sector, None

    metrics: dict = {}
    sectors: dict = {}
    if names:
        with ThreadPoolExecutor(max_workers=max(1, int(workers))) as pool:
            futures = [pool.submit(_work, n) for n in names]
            for fut in as_completed(futures):
                name, panel, sector, reason = fut.result()
                if reason is not None:
                    _drop(reason)
                    continue
                metrics[name] = panel
                sectors[name] = sector

    resolved = sorted(metrics)
    basis = (
        f"peer universe: {source}; resolved {len(resolved)}/{len(names)} names "
        f"with statements + sector; metrics f/m/z/o/gp_a/noa/accruals via "
        f"screen_ticker + normalized (capex_quality omitted: needs the annual "
        f"series); workers={workers}; universe={universe}"
    )
    return {
        "tickers": resolved,
        "n": len(resolved),
        "metrics": metrics,
        "sectors": sectors,
        "dropped": dropped,
        "basis": basis,
    }


def resolve_growth_medians(financials, sectors, *, min_n: int = 5) -> dict:
    """Peer-GROUP medians for the G-Score, from a peer universe (round-3 S10).

    The grouping is the caller's ``sectors`` map - a provider SECTOR label in
    this repo (``yfinance_sector.fetch_sector``), which is neither GICS nor an
    industry group. These are therefore peer-group medians over that grouping,
    which is what the G-Score legs compare a name against.

    ``financials``: ``{ticker: canonical fin}``; ``sectors``: ``{ticker:
    sector label}`` (the resolver's ``sectors`` map, or the screener's own
    column). Each cross-section is computed by
    ``quantitative_scores.growth_metrics`` - the same function ``growth_score``
    compares its own name against - and medianed within each sector by
    ``cross_section.group_median``, so the two paths cannot drift (rule 2).

    Returns ``{metric: {sector: {"median", "n"} | None}}`` for the seven
    G-Score inputs, plus a ``basis`` string. A sector below ``min_n`` maps to
    ``None``, and ``growth_score`` then excludes that leg with a printed
    reason rather than comparing against a handful of names.
    """
    from tradingagents.dataflows.quantitative_scores import growth_metrics
    from tradingagents.strategies.cross_section import group_median

    panels = {
        t: growth_metrics(fin)
        for t, fin in (financials or {}).items()
        if isinstance(fin, dict)
    }
    keys = (
        "roa",
        "cfo",
        "var_roa",
        "var_sales_growth",
        "rd_intensity",
        "capex_intensity",
        "ad_intensity",
    )
    out: dict = {}
    for key in keys:
        values = {t: p[key] for t, p in panels.items() if p.get(key) is not None}
        out[key] = group_median(values, sectors, min_n=min_n)
    covered = {k: sum(1 for v in out[k].values() if v) for k in keys}
    out["basis"] = (
        f"G-Score industry medians: {len(panels)} peer names partitioned by "
        f"sector label (min_n={min_n}); sectors with a median per metric "
        f"{covered}; metrics computed by growth_metrics (one definition)"
    )
    return out


def sector_medians_for(medians_by_sector: dict, sector: str | None) -> dict:
    """One name's ``{metric: {"median", "n"} | None}`` from the sector map.

    ``growth_score`` compares a name against ITS OWN sector's median, so the
    per-sector map ``resolve_growth_medians`` returns has to be selected down to
    one group per name. Unknown/None sector -> every median is None and the
    score excludes those legs (printed), never compares against another
    group's median. The ``basis`` key is not a metric and is skipped.
    """
    return {
        key: (value or {}).get(sector) if isinstance(value, dict) else None
        for key, value in (medians_by_sector or {}).items()
        if key != "basis"
    }


__all__ = ["resolve_peer_universe", "resolve_growth_medians", "sector_medians_for"]
