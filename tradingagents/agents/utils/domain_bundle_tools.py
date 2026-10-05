"""Composite domain-bundle tools (W4-1).

``strategies/domain_bundles.py`` ships per-analyst composite endpoints that
aggregate the fine-grained readers into one deterministic pass, so an analyst
makes ONE call instead of chaining micro-tools. They shipped with no agent
emitter (D3 triage, 2026-10-04): each was exported and importable, but bound to
no toolset, so no LLM could reach it. These wrappers bind them to the analysts
that own the claim.

Each wrapper returns the bundle's own dict rendered as one markdown block - the
composite's numbers, its ``data_quality`` flag and its ``missing_fields`` list
verbatim, so an unmeasured part reads as missing rather than absent. Advisory:
the values are the same computed reads the atomic tools return; the bundle only
changes HOW the analyst consumes them.
"""

from __future__ import annotations

from typing import Annotated

from langchain_core.tools import tool

_SKIP_KEYS = ("symbol", "effective_date", "domain", "data_quality",
              "missing_fields", "basket")


def _render(bundle: dict) -> str:
    """Render a bundle dict as one markdown block (each part verbatim)."""
    lines = [f"## {bundle.get('domain') or 'bundle'} — {bundle.get('symbol')}", ""]
    lines.append(f"- data quality: {bundle.get('data_quality')}")
    missing = bundle.get("missing_fields") or []
    lines.append(
        f"- missing: {', '.join(str(m) for m in missing) if missing else 'none'}"
    )
    for key, value in bundle.items():
        if key in _SKIP_KEYS:
            continue
        lines.append("")
        lines.append(f"### {key}")
        lines.append(str(value) if value is not None else "n/a")
    lines.append("")
    lines.append("computed composite, advisory - never a gate")
    return "\n".join(lines)


@tool
def get_market_technicals(
    ticker: Annotated[str, "ticker symbol"],
) -> str:
    """Composite market read (W4-1): regime + swing structure + momentum detail
    in ONE deterministic pass over the computed readers. Use it before any
    'the trend / regime / swing structure is X' claim, so one composite number
    is cited instead of chaining the atomic tools. Returns the bundle's
    ``data_quality`` and ``missing_fields`` verbatim; advisory, never a gate.
    """
    from tradingagents.strategies import domain_bundles

    try:
        return _render(domain_bundles.get_market_technicals(ticker))
    except Exception as exc:  # noqa: BLE001 - advisory, never blocks
        return f"market technicals bundle unavailable for {ticker}: {exc}"


@tool
def get_fundamental_profile(
    ticker: Annotated[str, "ticker symbol"],
) -> str:
    """Composite fundamental read (W4-1): value floors + valuation z + FCF yield
    + margin of safety in ONE PIT-gated pass. Use it before any 'it is cheap /
    expensive / has a floor' claim, so one composite cites the same PIT view
    instead of chaining the atomic tools. Returns the bundle's ``data_quality``
    and ``missing_fields`` verbatim; advisory, never a gate.
    """
    from tradingagents.strategies import domain_bundles

    try:
        return _render(domain_bundles.get_fundamental_profile(ticker))
    except Exception as exc:  # noqa: BLE001
        return f"fundamental profile bundle unavailable for {ticker}: {exc}"


@tool
def get_sentiment_flow_feed(
    ticker: Annotated[str, "ticker symbol"],
) -> str:
    """Composite sentiment/flow read (W4-1): news sentiment series + GDELT tone
    + order imbalance in ONE pass. Use it before any 'news sentiment / flow is
    X' claim, so one composite number is cited instead of chaining the atomic
    tools. Returns the bundle's ``data_quality`` and ``missing_fields``
    verbatim; advisory, never a gate.
    """
    from tradingagents.strategies import domain_bundles

    try:
        return _render(domain_bundles.get_sentiment_flow_feed(ticker))
    except Exception as exc:  # noqa: BLE001
        return f"sentiment flow feed bundle unavailable for {ticker}: {exc}"


@tool
def get_portfolio_risk_envelope(
    ticker: Annotated[str, "ticker symbol"],
    basket: Annotated[
        list | None, "optional basket of names for the whole-book envelope"
    ] = None,
) -> str:
    """Composite book-risk read (W4-1): the analyzed name's tail risk +
    liquidity read + the book tail risk in ONE pass. Use it before any
    'the book / this name can lose X' claim, so one composite number grounds
    the risk debate. Returns the bundle's ``data_quality`` and
    ``missing_fields`` verbatim; advisory, never a gate.
    """
    from tradingagents.strategies import domain_bundles

    try:
        return _render(domain_bundles.get_portfolio_risk_envelope(ticker, basket))
    except Exception as exc:  # noqa: BLE001
        return f"portfolio risk envelope bundle unavailable for {ticker}: {exc}"
