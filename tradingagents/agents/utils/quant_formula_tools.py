"""Agent-facing tools for the round-2 quant formula additions.

Docs: ``docs/design_quant_formulas_research_round2.md``,
``docs/implementation_plan_quant_formula_additions.md`` (phases Q1-Q6).

Each tool wraps one deterministic calculator and is gated by its own
``enable_*`` config key, default OFF. When the flag is off the tool returns a
clear DISABLED sentinel and never fabricates a value (the OpenBB-surface
convention in ``default_config.py``). Every line the tools emit names its basis
(window / estimator / sample), because the analyst must be able to cite it and
the report verifier must be able to check it.
"""

from __future__ import annotations

from typing import Annotated

from langchain_core.tools import tool

__all__ = [
    "get_spread_estimate",
    "get_return_decomposition",
    "get_quality_factors",
    "get_valuation_band",
    "get_disclosure_tone",
    "get_book_risk_budget",
    "QUANT_FORMULA_TOOLS",
]


def _flag(name: str, default: bool = False) -> bool:
    """Read an enable_* flag from the live config (never raises)."""
    try:
        from tradingagents.dataflows.config import get_config

        return bool((get_config() or {}).get(name, default))
    except Exception:  # noqa: BLE001 - a config read must never break a tool
        return default


def _disabled(tool_name: str, flag: str) -> str:
    return (
        f"{tool_name}: DISABLED (set {flag}=true / "
        f"TRADINGAGENTS_{flag.upper()}=true to enable). No value computed."
    )


@tool
def get_spread_estimate(
    ticker: Annotated[str, "ticker symbol"],
    current_date: Annotated[str | None, "current date you are trading at, yyyy-mm-dd"] = None,
) -> str:
    """Quote-free bid-ask spread floor from daily high/low prices (Q1).

    Corwin-Schultz and Abdi-Ranaldo estimates from the daily OHLC the engine
    already fetches - no quote feed needed, which is what makes it usable on
    names where quoted spreads are missing (mid-caps, HK names, sparse bars).
    The value is a daily cost FLOOR: quoted spreads stay authoritative when the
    vendor provides them. Cite before any 'trading cost / spread / round-trip
    slippage' claim on a name whose quoted spread is unavailable. Advisory.
    """
    if not _flag("enable_spread_estimator"):
        return _disabled("get_spread_estimate", "enable_spread_estimator")
    try:
        from tradingagents.agents.utils.analysis_tools import _ohlcv
        from tradingagents.strategies.liquidity_risk import spread_estimate

        ohlcv = _ohlcv(ticker)
        read = spread_estimate(
            ohlcv.get("closes") or [],
            ohlcv.get("highs") or [],
            ohlcv.get("lows") or [],
        )
        if not read:
            return (
                f"spread estimate {ticker}: unavailable (two-day range correction "
                "negative or too few bars - the estimators are undefined there)"
            )
        comp = read.get("components") or {}
        cs = comp.get("corwin-schultz")
        ar = comp.get("abdi-ranaldo")
        lines = [
            f"spread estimate {ticker}: {read['spread']:.5f} "
            f"({read['spread'] * 100:.2f}% of price)",
            f"  basis={read['basis']} n={read['n']}",
            f"  corwin-schultz={cs:.5f}" if cs is not None else "  corwin-schultz=n/a",
            f"  abdi-ranaldo={ar:.5f}" if ar is not None else "  abdi-ranaldo=n/a",
            "Interpretation: a cost FLOOR per name, not a quoted spread - quoted "
            "spreads win when available; gap days bias high-low estimators upward.",
        ]
        return "\n".join(lines)
    except Exception as exc:  # noqa: BLE001
        return f"spread estimate unavailable for {ticker}: {exc}"


@tool
def get_return_decomposition(
    ticker: Annotated[str, "ticker symbol"],
    current_date: Annotated[str | None, "current date you are trading at, yyyy-mm-dd"] = None,
) -> str:
    """Overnight vs intraday decomposition of a name's returns (Q5).

    Splits the daily log return into its intraday leg (close/open) and its
    overnight leg (open/previous close) and reports the share of variance each
    carries. Use before any 'this dip is being sold intraday / the move is all
    overnight news / gap risk' claim - it says WHICH LEG carried the move, never
    why (it is a decomposition, not an attribution). Advisory.
    """
    if not _flag("enable_return_decomposition"):
        return _disabled("get_return_decomposition", "enable_return_decomposition")
    try:
        from tradingagents.agents.utils.analysis_tools import _ohlcv
        from tradingagents.strategies.market_session import decompose_returns

        ohlcv = _ohlcv(ticker)
        read = decompose_returns(ohlcv.get("opens") or [], ohlcv.get("closes") or [])
        if not read:
            return (
                f"return decomposition {ticker}: unavailable (needs opens with "
                "matching closes and non-zero total variance)"
            )
        share = read["intraday_var_share"]
        lines = [
            f"return decomposition {ticker}: n={read['n']} bars",
            f"  intraday mean={read['intraday_mean']:+.4%} vol={read['intraday_vol']:.4%}",
            f"  overnight mean={read['overnight_mean']:+.4%} vol={read['overnight_vol']:.4%}",
            f"  intraday share of total variance={share:.1%}",
            "Interpretation: which leg carried the move (intraday = the "
            "mean-reversion case this book trades; overnight = gap risk an ATR "
            "stop protects worst against). Not a cause.",
        ]
        return "\n".join(lines)
    except Exception as exc:  # noqa: BLE001
        return f"return decomposition unavailable for {ticker}: {exc}"


@tool
def get_quality_factors(
    ticker: Annotated[str, "ticker symbol"],
    current_date: Annotated[str | None, "current date you are trading at, yyyy-mm-dd"] = None,
) -> str:
    """Gross profitability and net operating assets from the statements (Q4).

    GP/A = (revenue - COGS) / total assets (Novy-Marx 2013) and NOA =
    (operating assets - operating liabilities) / prior total assets
    (Hirshleifer et al. 2004). Complements the distress screens (Piotroski /
    Beneish / Ohlson) with the 'is this a good business' question a dip screen
    otherwise leaves open. Cite before any 'cheap quality name / value trap /
    balance-sheet bloat' claim. Missing COGS or prior-year assets render
    unavailable - never substituted. Advisory.
    """
    try:
        from tradingagents.dataflows.quantitative_scores import (
            gross_profitability,
            net_operating_assets,
        )
        from tradingagents.dataflows.statement_parsing import fetch_ticker

        fin = fetch_ticker(ticker, current_date or "") or {}
        gp = gross_profitability(fin) if fin else None
        noa = net_operating_assets(fin) if fin else None
        if not gp and not noa:
            return (
                f"quality factors {ticker}: unavailable (needs revenue/COGS/total "
                "assets and a prior-year balance sheet)"
            )
        lines = [f"quality factors {ticker}:"]
        if gp:
            lines.append(f"  gp_a={gp['value']:.4f} ({gp['classification']}; {gp['basis']})")
        else:
            lines.append("  gp_a=unavailable (revenue/COGS/total assets missing)")
        if noa:
            lines.append(f"  noa={noa['value']:+.4f} ({noa['classification']}; {noa['basis']})")
        else:
            lines.append("  noa=unavailable (needs two consecutive balance sheets)")
        lines.append(
            "Interpretation: GP/A is a quality counterweight to cheapness; high "
            "NOA (bloated balance sheet) is a documented drag on forward returns."
        )
        return "\n".join(lines)
    except Exception as exc:  # noqa: BLE001
        return f"quality factors unavailable for {ticker}: {exc}"


@tool
def get_valuation_band(
    ticker: Annotated[str, "ticker symbol"],
    point_value: Annotated[float | None, "the model fair value / price target being cited"] = None,
    current_date: Annotated[str | None, "current date you are trading at, yyyy-mm-dd"] = None,
    alpha: Annotated[float | None, "miscoverage level (default: config conformal_alpha)"] = None,
) -> str:
    """Calibrated band around a model valuation (Q3, conformal prediction).

    Wraps a point fair value in a band whose coverage was measured on a
    calibration set of model-vs-realized pairs, and always prints the REALIZED
    coverage next to the nominal level (a bare '90% band' would overclaim: the
    guarantee is marginal and only under exchangeability, which markets break).

    Prerequisite: at least ``conformal_min_pairs`` model-vs-realized pairs.
    Supply them via the ``pairs`` ledger
    ``<results_dir>/<TICKER>/valuation_pairs.jsonl`` (one ``[predicted, actual]``
    array per line). Without them the tool says so and leaves the point value
    unbanded - it never invents an interval. Cite the band before any 'trading
    at an X% discount to fair value' claim; a value inside the band is not a
    signal. Advisory.
    """
    if not _flag("enable_conformal_bands"):
        return _disabled("get_valuation_band", "enable_conformal_bands")
    try:
        from tradingagents.strategies.conformal import rolling_band

        pairs = _load_valuation_pairs(ticker)
        if not pairs:
            suffix = f" point value {point_value} left unbanded." if point_value is not None else ""
            return (
                f"valuation band {ticker}: unavailable - needs model-vs-realized "
                "pairs at <results_dir>/<TICKER>/valuation_pairs.jsonl "
                "(one [predicted, actual] array per line)." + suffix
            )
        from tradingagents.dataflows.config import get_config

        cfg = get_config() or {}
        a = float(alpha if alpha is not None else cfg.get("conformal_alpha", 0.1))
        min_n = int(cfg.get("conformal_min_pairs", 40))
        window = int(cfg.get("conformal_window", 250))
        read = rolling_band(pairs, window=window, alpha=a, min_n=min_n)
        if not read:
            return (
                f"valuation band {ticker}: unavailable - {len(pairs)} pair(s) "
                f"below the {min_n}-pair floor (no uncalibrated interval is reported)"
            )
        lines = [
            f"valuation band {ticker} (nominal {read['nominal']:.0%}, "
            f"realized {read['realized_coverage']:.1%} on {read['n']} pairs, "
            f"window {read['window']}):",
            f"  [{read['low']:.4f}, {read['high']:.4f}]",
        ]
        if point_value is not None:
            inside = read["low"] <= float(point_value) <= read["high"]
            lines.append(
                f"  point value {float(point_value):.4f} is "
                f"{'INSIDE' if inside else 'OUTSIDE'} the band"
            )
        lines.append(
            "Interpretation: the band is what the model's past error distribution "
            "supports, not a target; realized coverage is quoted because the "
            "exchangeability assumption is imperfect in markets."
        )
        return "\n".join(lines)
    except Exception as exc:  # noqa: BLE001
        return f"valuation band unavailable for {ticker}: {exc}"


def _load_valuation_pairs(ticker: str) -> list:
    """Read the per-ticker model-vs-realized ledger (best effort, never raises)."""
    import json
    import os

    try:
        from tradingagents.dataflows.config import get_config

        cfg = get_config() or {}
        results_dir = cfg.get("results_dir") or os.path.join("reports", "")
        path = os.path.join(str(results_dir), str(ticker).upper(), "valuation_pairs.jsonl")
        if not os.path.exists(path):
            return []
        out = []
        with open(path, encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                try:
                    row = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if isinstance(row, (list, tuple)) and len(row) == 2:
                    try:
                        out.append((float(row[0]), float(row[1])))
                    except (TypeError, ValueError):
                        continue
        return out
    except Exception:  # noqa: BLE001 - a missing ledger is 'no pairs', not a crash
        return []


@tool
def get_disclosure_tone(
    ticker: Annotated[str, "ticker symbol"],
    current_date: Annotated[str | None, "current date you are trading at, yyyy-mm-dd"] = None,
) -> str:
    """Dictionary tone, readability and document divergence (Q6).

    Loughran-McDonald-style tone counts and a readability score over the text
    the news path already fetches, plus - when two documents for the same firm
    are available - the tone and complexity GAP between them (the 2025
    disclosure evidence: tone divergence is short-lived, complexity divergence
    persists). Deterministic and reproducible, so it can be cited beside the
    model's narrative read and checked against it. Counts and the dictionary
    version are always reported. Advisory.
    """
    if not _flag("enable_text_factors"):
        return _disabled("get_disclosure_tone", "enable_text_factors")
    try:
        from tradingagents.strategies.text_factors import divergence, lm_tone, readability

        news_text = _fetch_news_text(ticker, current_date)
        if not news_text:
            return f"disclosure tone {ticker}: unavailable (no text source returned content)"
        tone = lm_tone(news_text)
        read = readability(news_text)
        if not tone or not read:
            return f"disclosure tone {ticker}: unavailable (text had no words)"
        lines = [f"disclosure tone {ticker} (dictionary {tone['dictionary']}, {tone['words']} words):"]
        if tone["tone"] is None:
            lines.append(f"  tone=zero_hits (0 of {tone['words']} words in the dictionary)")
        else:
            lines.append(
                f"  tone={tone['tone']:+.4f} (neg={tone['negative']} pos={tone['positive']} "
                f"uncertainty={tone['uncertainty']} litigious={tone['litigious']})"
            )
        lines.append(
            f"  readability: fog={read['fog']:.2f} fk_grade={read['fk_grade']:.2f} "
            f"ease={read['reading_ease']:.1f}"
        )
        filing_text = _fetch_filing_text(ticker, current_date)
        if filing_text:
            div = divergence(filing_text, news_text)
            if div:
                lines.append(
                    f"  filing-vs-news tone_gap={div['tone_gap']:+.4f} "
                    f"({div['tone_direction']}), complexity_gap={div['complexity_gap']:+.2f} "
                    f"({div['complexity_direction']})"
                )
        else:
            lines.append(
                "  divergence=unavailable (needs a second document for the same period)"
            )
        lines.append(
            "Interpretation: a deterministic second opinion beside the narrative "
            "read - zero_hits means no signal found, NOT neutral. Period-dependent; "
            "always quote the counts."
        )
        return "\n".join(lines)
    except Exception as exc:  # noqa: BLE001
        return f"disclosure tone unavailable for {ticker}: {exc}"


def _fetch_news_text(ticker: str, current_date: str | None) -> str:
    """Recent news text for the ticker via the same vendor route the news path uses."""
    try:
        from tradingagents.dataflows.interface import route_to_vendor

        raw = route_to_vendor("get_news", ticker, current_date or "", current_date or "")
        return raw if isinstance(raw, str) else ""
    except Exception:  # noqa: BLE001 - absent text is 'unavailable', never a crash
        return ""


def _fetch_filing_text(ticker: str, current_date: str | None) -> str:
    """Recent filing text for the ticker, when the routed source returns prose."""
    try:
        from tradingagents.dataflows.interface import route_to_vendor

        raw = route_to_vendor("get_sec_filings", ticker, current_date or "")
        text = raw if isinstance(raw, str) else ""
        # A metadata-only listing is not a document: require prose-length text.
        return text if len(text) > 600 else ""
    except Exception:  # noqa: BLE001 - absent text is 'unavailable', never a crash
        return ""


@tool
def get_book_risk_budget(
    current_date: Annotated[str | None, "current date you are trading at, yyyy-mm-dd"] = None,
) -> str:
    """Book sizing under the CVaR budget: minimum-CVaR weights (Q2).

    The gate today MEASURES book CVaR/CDaR and blocks; this solves for weights
    under the same budget (Rockafellar-Uryasev sample-average LP) using the
    configured risk basket, with joint-tail copula scenarios in place of the
    single fixed -10% shock. Advisory sizing only - never an order. Use before
    any 'size the book down / the book is over its budget' claim.
    """
    if not _flag("enable_book_risk_sizing"):
        return _disabled("get_book_risk_budget", "enable_book_risk_sizing")
    try:
        from tradingagents.agents.utils.analysis_tools import _daily_returns, _ohlcv
        from tradingagents.dataflows.config import get_config
        from tradingagents.strategies.book_risk import copula_scenarios, min_cvar_weights

        cfg = get_config() or {}
        weights = dict(cfg.get("risk_basket_weights") or {})
        tickers = list(cfg.get("risk_basket_tickers") or weights)
        if not weights:
            weights = {t: 1.0 / max(1, len(tickers)) for t in tickers}
        returns_by_name = {}
        for name in tickers:
            rets = _daily_returns(_ohlcv(name).get("closes") or [])
            if len(rets) >= 30:
                returns_by_name[name] = rets
        if len(returns_by_name) < 2:
            return (
                "book risk budget: unavailable (needs >= 2 basket names with >= 30 "
                "return observations)"
            )
        cap = float(cfg.get("max_position_pct", 0.30))
        alpha = float(cfg.get("risk_daily_cvar_budget_pct", 0.03))
        min_n = int(cfg.get("book_risk_sizing_min_scenarios", 60))
        max_delta = float(cfg.get("book_risk_sizing_max_delta", 0.05))
        scenarios = copula_scenarios(returns_by_name) or None
        solve = min_cvar_weights(
            returns_by_name,
            alpha=alpha,
            cap=cap,
            max_delta=max_delta,
            current=weights,
            min_scenarios=min_n,
        )
        if not solve:
            return (
                f"book risk budget: unavailable - below the {min_n}-scenario floor "
                "or fewer than 2 measurable names (no fabricated weights)"
            )
        cur = ", ".join(f"{k}={v:.1%}" for k, v in sorted(weights.items()))
        tgt = ", ".join(f"{k}={v:.1%}" for k, v in sorted(solve["weights"].items()))
        lines = [
            f"book risk budget (alpha={solve['alpha']:.2%} daily, n={solve['n']}, "
            f"binding={solve['binding']}):",
            f"  current: {cur or 'n/a'}",
            f"  target:  {tgt}",
            f"  book CVaR {solve['cvar']:.4%}" + (f" | CDaR {solve['cdar']:.4%}" if solve.get("cdar") is not None else ""),
            f"  scenarios: {'t-copula joint tail' if scenarios else 'historical only'}",
            "Interpretation: advisory sizing under the existing budget - the "
            "governor still owns PASS/WARN/REJECT; nothing here is an order.",
        ]
        return "\n".join(lines)
    except Exception as exc:  # noqa: BLE001
        return f"book risk budget unavailable: {exc}"


QUANT_FORMULA_TOOLS = [
    get_spread_estimate,
    get_return_decomposition,
    get_quality_factors,
    get_valuation_band,
    get_disclosure_tone,
    get_book_risk_budget,
]
