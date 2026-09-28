"""Analyst-rating and earnings-calendar tools (Finnhub-backed)."""
from typing import Annotated

from langchain_core.tools import tool

from tradingagents.dataflows.date_window import as_of, get_run_trade_date
from tradingagents.dataflows.interface import route_to_vendor


@tool
def get_analyst_ratings(
    ticker: Annotated[str, "ticker symbol"],
) -> str:
    """
    Retrieve sell-side analyst ratings and price-target consensus for a ticker.
    Returns the recommendation trend (strong buy / buy / hold / sell /
    strong sell counts per period) and the price-target consensus (mean,
    median, high, low, and number of analysts). Uses the configured
    analyst_ratings vendor.

    Args:
        ticker (str): Ticker symbol of the company

    Returns:
        str: A formatted report of analyst ratings and price targets
    """
    text = route_to_vendor("get_analyst_ratings", ticker)
    return text + _pt_revision_note(ticker)


@tool
def get_earnings_calendar(
    ticker: Annotated[str, "ticker symbol"],
    curr_date: Annotated[str, "current date you are trading at, yyyy-mm-dd"],
    look_ahead_days: Annotated[
        int | None, "Days to look AHEAD from curr_date; omit for a 30-day window"
    ] = None,
) -> str:
    """
    Retrieve the upcoming earnings date and last reported EPS surprise for a
    ticker. Returns earnings date, EPS estimate, EPS actual, surprise percent,
    and revenue estimate. Uses the configured earnings_calendar vendor.

    Args:
        ticker (str): Ticker symbol of the company
        curr_date (str): Current date in yyyy-mm-dd format
        look_ahead_days (int): FORWARD window to the next print; omit for 30 days

    Returns:
        str: A formatted report of upcoming earnings and EPS surprise
    """
    return route_to_vendor(
        "get_earnings_calendar", ticker, as_of(curr_date, get_run_trade_date()), look_ahead_days
    )

def _pt_revision_note(ticker: str) -> str:
    """Record this run's PT consensus, then print the accumulated revision.

    NEWS-6. Every vendor serves a current consensus only, so a price-target
    revision is not observable from a single call - it exists only once
    snapshots have accumulated in ``strategies/pt_history``. This is the writer:
    a dataflow never writes the store, matching the split ``score_history``
    already uses (written from ``graph/trading_graph.py:749``). Advisory - any
    failure returns "" and never breaks the ratings leaf.
    """
    try:
        from tradingagents.dataflows.price_targets import price_target_snapshot
        from tradingagents.strategies.pt_history import pt_revision, record_pt_snapshot

        record_pt_snapshot(ticker, price_target_snapshot(ticker))
        read = pt_revision(ticker)
    except Exception:  # noqa: BLE001 - advisory, never fatal
        return ""

    lines = ["\n\n### Price-target revision (accumulated, advisory)"]
    if read.get("source"):
        lines.append(
            f"- recorded consensus: mean {read['latest_mean']} (source "
            f"{read['source']}) - the store is fed by the yfinance target chain, "
            f"which may differ from the vendor that rendered the consensus above"
        )
    if read.get("revision") is None:
        lines.append(f"- unavailable: {read.get('reason')}")
        lines.append(
            f"- the vendors serve a CURRENT consensus only, so a revision exists "
            f"only after this store has accumulated snapshots; {read.get('observations')} "
            f"observation(s) recorded so far"
        )
    else:
        pct = read.get("revision_pct")
        pct_txt = f"{pct:+.2f}%" if pct is not None else "n/a (no prior base)"
        lines.append(
            f"- revision {read['revision']:+.2f} ({pct_txt}) from "
            f"{read['prior_date']} to {read['latest_date']} - {read['direction']}"
        )
        lines.append(
            f"- since the first observation ({read['span'][0]}): "
            f"{read['revision_since_first']:+.2f} over {read['observations']} observation(s)"
        )
    lines.append(
        "- basis: snapshots of the consensus, one row per date, never rewritten; "
        "the vendors carry no per-analyst history, so this series starts when the "
        "store does. Informs, never gates."
    )
    return "\n".join(lines) + "\n"
