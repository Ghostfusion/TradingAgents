"""Benzinga event-surface tools: guidance, FDA milestones, offerings, analyst
actions and news retractions.

Five capabilities that had **no producer at all** in this repo before
2026-09-20, all served by the same registered Benzinga key:

- ``get_guidance_revisions`` - management's own forward revenue/EPS range. The
  only forward *growth* producer in the data layer; the fundamental engine's
  ``rev_cagr5`` is trailing and comes back NA when the statement history is
  short.
- ``get_fda_calendar`` - regulatory milestones (approvals, rejections, trial
  results). Sparse for a non-biopharma issuer, which is a correct answer.
- ``get_offerings_calendar`` - secondary offerings, i.e. dilution.
- ``get_analyst_actions`` - individual actions with the firm and the
  price-target move. The *event* view, complementary to the consensus snapshot
  ``get_analyst_ratings`` returns.
- ``get_news_removed`` - retracted article ids. The only feed here that can
  **invalidate** evidence already collected.

All five are behind ``enable_benzinga_surface`` (default OFF). While it is off
each tool returns a DISABLED sentinel and never fabricates, so a gate-off run is
byte-identical to the run before the surface existed.
"""

from typing import Annotated

from langchain_core.tools import tool

from tradingagents.agents.utils.analysis_tools import _feature_gate
from tradingagents.dataflows.interface import route_to_vendor


@tool
def get_guidance_revisions(
    ticker: Annotated[str, "ticker symbol"],
    start_date: Annotated[str, "window start, yyyy-mm-dd"],
    end_date: Annotated[str, "window end, yyyy-mm-dd"],
) -> str:
    """Corporate guidance revisions: management's own forward revenue and EPS
    range for a named future period, with the prior range when the vendor
    carries one, plus the vendor's narrative note.

    This is forward guidance, not a reported figure - use it before any
    'management guided / next-period growth' claim, and never substitute it for
    an actual. Opt-in (default off).
    """
    gate = _feature_gate("enable_benzinga_surface", "TRADINGAGENTS_ENABLE_BENZINGA_SURFACE")
    if gate:
        return gate
    return str(route_to_vendor("get_guidance_revisions", ticker, start_date, end_date))


@tool
def get_fda_calendar(
    ticker: Annotated[str, "ticker symbol"],
    start_date: Annotated[str, "window start, yyyy-mm-dd"],
    end_date: Annotated[str, "window end, yyyy-mm-dd"],
) -> str:
    """FDA and clinical milestones for a ticker: approvals, rejections, trial
    results, with the drug, the indication, the co-sponsors and the outcome.

    Use before any 'regulatory catalyst / approval / trial readout' claim. An
    empty window is normal for a non-biopharma issuer and returns a typed
    no-data signal rather than a bare heading. Opt-in (default off).
    """
    gate = _feature_gate("enable_benzinga_surface", "TRADINGAGENTS_ENABLE_BENZINGA_SURFACE")
    if gate:
        return gate
    return str(route_to_vendor("get_fda_calendar", ticker, start_date, end_date))


@tool
def get_offerings_calendar(
    ticker: Annotated[str, "ticker symbol"],
    start_date: Annotated[str, "window start, yyyy-mm-dd"],
    end_date: Annotated[str, "window end, yyyy-mm-dd"],
) -> str:
    """Secondary offerings for a ticker: shares issued, the price, the gross
    size, whether the paper came off a shelf, and the type.

    A dilution signal - use it before any 'share count / dilution / overhang'
    claim. The whole US market produces only a handful of rows per year, so an
    empty window is expected. Opt-in (default off).
    """
    gate = _feature_gate("enable_benzinga_surface", "TRADINGAGENTS_ENABLE_BENZINGA_SURFACE")
    if gate:
        return gate
    return str(route_to_vendor("get_offerings_calendar", ticker, start_date, end_date))


@tool
def get_analyst_actions(
    ticker: Annotated[str, "ticker symbol"],
    start_date: Annotated[str, "window start, yyyy-mm-dd"],
    end_date: Annotated[str, "window end, yyyy-mm-dd"],
) -> str:
    """Individual sell-side analyst actions for a ticker: the firm, the analyst,
    what changed (rating and/or price target) and the size of the target move.

    This is the event view - who revised and in which direction - and is
    complementary to `get_analyst_ratings`, which returns the consensus
    snapshot. Use it before any 'analyst revision momentum' claim. Opt-in
    (default off).
    """
    gate = _feature_gate("enable_benzinga_surface", "TRADINGAGENTS_ENABLE_BENZINGA_SURFACE")
    if gate:
        return gate
    return str(route_to_vendor("get_analyst_actions", ticker, start_date, end_date))


@tool
def get_news_removed(
    limit: Annotated[int, "how many retraction ids to return, default 100"] = 100,
    page: Annotated[int, "1-based page of the retraction stream, default 1"] = 1,
) -> str:
    """Retracted article ids from the newswire: the ids Benzinga has withdrawn.

    The only feed here that can **invalidate** evidence already collected. Cite
    it before any 'the headline said X' claim: if a headline used in a report
    appears in this list, that evidence is withdrawn and must be dropped rather
    than argued around.

    Takes no ticker and no date window: the endpoint silently ignores every date
    parameter (measured 2026-09-20 - an empty filter, a one-day window and a
    three-month window all return the identical rows), so this reader offers a
    limit and a page and never claims to filter by date. Opt-in (default off).
    """
    gate = _feature_gate("enable_benzinga_surface", "TRADINGAGENTS_ENABLE_BENZINGA_SURFACE")
    if gate:
        return gate
    return str(route_to_vendor("get_news_removed", limit, page))


BENZINGA_TOOLS = [
    get_guidance_revisions,
    get_fda_calendar,
    get_offerings_calendar,
    get_analyst_actions,
    get_news_removed,
]

__all__ = [
    "BENZINGA_TOOLS",
    "get_analyst_actions",
    "get_fda_calendar",
    "get_guidance_revisions",
    "get_news_removed",
    "get_offerings_calendar",
]
