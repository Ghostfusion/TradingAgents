"""The caller's book, as the decision agents see it.

Optional input to a run: what is held and how much cash is unallocated. Three
states are distinct and MUST stay so: a position, a genuinely flat book, and
NO context at all. Treating "not provided" as "flat" would invent a fact
about the caller's account (upstream ``portfolio.py``).

Broker-neutral by construction: weights are generic fractions of the book and
the currency is whatever label the caller passes, so nothing here implies a
venue or an execution path. The book lives in the repo's ONE representation
(``holdings_tickers`` / ``holdings_weights``, else the risk basket) - this
module only renders it, it never introduces a second book format.
"""

from __future__ import annotations

from typing import Any

# Rendered whenever no book was supplied. It states the absence AND refuses
# to infer anything about the account, so a model can never read silence as
# "the caller is flat".
NO_CONTEXT_LINE = (
    "Portfolio context: none supplied for this run - no book was provided. "
    "This says nothing about the account: do NOT assume the book is flat and "
    "do NOT assume any position is held or not held."
)


def build_portfolio_context(cfg: dict | None) -> dict[str, Any] | None:
    """Portfolio context from the configured book, or ``None`` when none is set.

    Reads ``holdings_tickers`` / ``holdings_weights`` when set, else the risk
    basket - the repo's ONE book representation. A configured book becomes a
    ``{"positions": [{"ticker", "weight"}], "cash", "currency"}`` dict; an
    unset book returns ``None`` so callers render the no-context state rather
    than a flat book. Positions are sorted (weight desc, then ticker) so the
    rendering and its fingerprint are order-stable.
    """
    cfg = cfg or {}
    tickers = list(cfg.get("holdings_tickers") or cfg.get("risk_basket_tickers") or [])
    weights = dict(cfg.get("holdings_weights") or cfg.get("risk_basket_weights") or {})
    if not tickers:
        return None
    if not weights:
        weights = {s: 1.0 / len(tickers) for s in tickers}
    positions = [
        {"ticker": str(s), "weight": float(w)}
        for s, w in weights.items()
        if w and w > 0
    ]
    positions.sort(key=lambda p: (-p["weight"], p["ticker"]))
    total = sum(p["weight"] for p in positions)
    return {
        "positions": positions,
        "cash": max(0.0, 1.0 - total),
        "currency": None,
    }


def render_portfolio_context(portfolio_context: Any, ticker: str) -> str:
    """The portfolio block for the decision agents, three states kept distinct.

    - ``None``/empty -> :data:`NO_CONTEXT_LINE` (never a flat book).
    - a supplied book without the analyzed name -> "No current position in X"
      (a genuinely flat holding for that name).
    - a supplied book with the analyzed name -> its position line.
    """
    if not portfolio_context:
        return NO_CONTEXT_LINE

    symbol = str(ticker or "").strip().upper()
    positions = [
        p for p in (portfolio_context.get("positions") or []) if isinstance(p, dict)
    ]
    held = next(
        (p for p in positions if str(p.get("ticker", "")).strip().upper() == symbol),
        None,
    )

    lines = ["Portfolio at the analysis date:"]
    if held is None:
        # The book WAS supplied and does not list the name: this is a real
        # flat position, not an absent context.
        lines.append(f"- No current position in {symbol}: not held in the supplied book")
    else:
        qty = held.get("quantity")
        weight = held.get("weight")
        price = held.get("average_price")
        if qty is not None:
            detail = f"{qty:,.4g} units"
        elif weight is not None:
            detail = f"{weight * 100:.1f}% of book"
        else:
            detail = "position held"
        if price is not None:
            detail += f", average price {price:,.2f}"
        lines.append(f"- Current position in {symbol}: {detail}")

    cash = portfolio_context.get("cash")
    currency = portfolio_context.get("currency")
    if cash is not None:
        suffix = f" {currency}" if currency else ""
        lines.append(f"- Cash/unallocated: {cash * 100:.1f}%{suffix}")

    others = [p for p in positions if p is not held]
    if others:
        rendered = ", ".join(
            f"{str(p.get('ticker', '')).strip().upper()} {p['weight'] * 100:.1f}%"
            for p in others
            if p.get("weight") is not None
        )
        if rendered:
            lines.append(f"- Other positions: {rendered}")
    return "\n".join(lines)
