"""Book positions -> risk-basket weights (analysis-only, advisory).

Reads broker portfolio CSV exports (Fidelity-style: Account number / Symbol /
Quantity / Current value / Percent of account / Type, with money-market and
unsettled rows) and turns the FULL book - including cash - into the
``TRADINGAGENTS_RISK_BASKET_TICKERS`` / ``TRADINGAGENTS_RISK_BASKET_WEIGHTS``
.env format the risk governor and (Option A) the PM holdings block consume.

Design decisions:
- **Cash is included in the denominator**: a weight is a fraction of the whole
  book (positions + cash). The repo's ``portfolio_cvar`` already treats a
  basket weight-sum < 1.0 as "weights + implicit zero-return cash", so the
  gate and the holdings read stay consistent and the residual IS the cash
  sleeve (never emitted as a ticker - CASH has no vendor data).
- **Cash detection is NOT the broker's Type column** (Fidelity labels every
  row "Cash", including equities). Cash/money-market/unsettled rows are
  detected by markers: ``**`` suffix (SPAXX** / FDRXX**), blank Symbol with a
  value (unsettled/accrual), or empty Quantity with a sweep description.
- **Symbols normalize** through ``dataflows.symbol_utils.normalize_symbol`` so
  basket members resolve on the vendor chain (BRK.B -> BRK-B).
- **No-fabrication**: a row with a symbol but no usable value is skipped with
  a reason; a weight is rendered only when its value is measurable.
"""

from __future__ import annotations

from dataclasses import dataclass

# Fidelity marks money-market / sweep funds with a trailing ``**`` (SPAXX**).
_CASH_SUFFIX = "**"
# Blank-Quantity rows whose Symbol / Description marks them as settlement or
# sweep lines are cash: sweep descriptions ("HELD IN MONEY MARKET") and
# Fidelity's unsettled-settlement label ("Pending activity").
_CASH_DESC_KEYWORDS = ("money market", "sweep", "cash", "spaxx", "fdrxx", "fdic")
_CASH_SYMBOL_KEYWORDS = ("pending",)


def _to_float(v) -> float | None:
    """Parse a broker numeric cell ($/commas/% stripped); None when blank."""
    if v is None:
        return None
    s = str(v).replace("$", "").replace(",", "").replace("%", "").strip()
    if not s:
        return None
    try:
        return float(s)
    except (TypeError, ValueError):
        return None


def is_cash_row(row: dict) -> bool:
    """True when a CSV row is a cash / money-market / sweep / unsettled item.

    Heuristic order: ``**`` suffix (Fidelity money-market marker, e.g.
    ``SPAXX**`` / ``FDRXX**``) -> blank Symbol with a value (unsettled /
    accrual row) -> empty Quantity with a sweep description. The broker's
    Type column is deliberately NOT consulted: Fidelity labels equities
    "Cash" too.
    """
    symbol = str(row.get("Symbol") or "").strip()
    if symbol.endswith(_CASH_SUFFIX):
        return True
    value = _to_float(row.get("Current value"))
    if not symbol and value is not None:
        return True
    if symbol and _to_float(row.get("Quantity")) is None:
        desc = str(row.get("Description") or "").lower()
        if any(kw in desc for kw in _CASH_DESC_KEYWORDS):
            return True
        if any(kw in symbol.lower() for kw in _CASH_SYMBOL_KEYWORDS):
            return True
    return False


@dataclass(frozen=True)
class PositionRow:
    """One non-cash position parsed from a broker export."""

    symbol: str
    value: float
    quantity: float | None = None
    account: str = ""
    description: str = ""


def _normalize_symbol(symbol: str) -> str:
    from tradingagents.dataflows.symbol_utils import normalize_symbol

    return normalize_symbol(symbol)


def parse_rows(rows, account: str = "") -> tuple[list[PositionRow], list[str]]:
    """Parse broker CSV rows -> (positions, skipped reasons).

    Empty / trailer rows and cash rows are skipped silently; a row with a
    symbol but no measurable value is skipped with a reason (no fabrication).
    Symbols are normalized (BRK.B -> BRK-B) so the basket resolves on the
    vendor chain.
    """
    out: list[PositionRow] = []
    skipped: list[str] = []
    for i, row in enumerate(rows or []):
        if not row or not isinstance(row, dict):
            continue
        symbol = str(row.get("Symbol") or "").strip()
        if not symbol:
            continue  # trailer / blank row
        if is_cash_row(row):
            continue
        value = _to_float(row.get("Current value"))
        if value is None or value <= 0:
            skipped.append(f"{symbol} (row {i + 1}): no usable Current value")
            continue
        out.append(
            PositionRow(
                symbol=_normalize_symbol(symbol),
                value=value,
                quantity=_to_float(row.get("Quantity")),
                account=str(account or ""),
                description=str(row.get("Description") or "").strip(),
            )
        )
    return out, skipped


def _broker_pct_sum(rows) -> float:
    """Sum of the broker's own 'Percent of account' column (cross-check)."""
    return sum(
        (x or 0.0)
        for x in (_to_float(r.get("Percent of account")) for r in (rows or []))
    )


def book_stats(rows_by_account: dict[str, list]) -> dict:
    """Full-book summary from raw CSV rows per account.

    Returns ``{positions: {symbol: total_value}, cash_value, total_value,
    per_account: {...}, skipped: [...]}``. ``total_value`` INCLUDES cash so a
    weight is a fraction of the whole book.
    """
    positions: dict[str, float] = {}
    cash = 0.0
    per_account: dict[str, dict] = {}
    skipped: list[str] = []
    for account, rows in (rows_by_account or {}).items():
        poss, skips = parse_rows(rows, account=account)
        skipped.extend(f"{account}: {s}" for s in skips)
        acct_cash = 0.0
        for row in rows or []:
            if is_cash_row(row):
                v = _to_float(row.get("Current value"))
                if v is not None:
                    acct_cash += v
        cash += acct_cash
        for p in poss:
            positions[p.symbol] = positions.get(p.symbol, 0.0) + p.value
        per_account[account] = {
            "positions": poss,
            "cash_value": acct_cash,
            "broker_pct_sum": _broker_pct_sum(rows),
        }
    total = sum(positions.values()) + cash
    return {
        "positions": positions,
        "cash_value": round(cash, 2),
        "total_value": round(total, 2),
        "per_account": per_account,
        "skipped": skipped,
    }


def compute_weights(
    positions_by_symbol: dict[str, float],
    cash_value: float,
    min_value: float = 0.0,
) -> dict[str, float]:
    """Weights as a fraction of the WHOLE book (positions + cash), desc, 4dp.

    ``min_value`` drops positions whose dollar value is below the floor
    (dust filter). Cash is included in the denominator but never emitted as
    a ticker; the weight-sum < 1.0 residual IS the cash sleeve (the repo's
    documented ``portfolio_cvar`` cash semantic).
    """
    pairs = {s: v for s, v in (positions_by_symbol or {}).items() if v >= min_value}
    total = sum(pairs.values()) + max(cash_value, 0.0)
    if total <= 0:
        return {}
    out = {s: round(v / total, 4) for s, v in pairs.items()}
    out = {s: w for s, w in out.items() if w > 0}
    return dict(sorted(out.items(), key=lambda kv: (-kv[1], kv[0])))


def render_env_basket(weights: dict[str, float]) -> tuple[str, str]:
    """(TICKERS_LINE, WEIGHTS_LINE) in the exact .env format.

    Round-trips through ``default_config._coerce`` (4dp with trailing zeros,
    e.g. ``AVGO=0.0268,BAC=0.0060`` -> dict {"AVGO": 0.0268, ...}).
    """
    tickers = ",".join(weights)
    pairs = ",".join(f"{sym}={wgt:.4f}" for sym, wgt in weights.items())
    return tickers, pairs


def patch_env_text(text: str, tickers_line: str, weights_line: str) -> str:
    """Replace the two basket lines in .env text; other lines byte-identical.

    A missing mandatory line is appended at the end (respects the file's
    trailing-newline convention). Idempotent for repeated runs.
    """
    t_key = "TRADINGAGENTS_RISK_BASKET_TICKERS="
    w_key = "TRADINGAGENTS_RISK_BASKET_WEIGHTS="
    new_t, new_w = f"{t_key}{tickers_line}\n", f"{w_key}{weights_line}\n"
    found_t = found_w = False
    out = []
    for ln in text.splitlines(keepends=True):
        if ln.startswith(t_key):
            out.append(new_t)
            found_t = True
        elif ln.startswith(w_key):
            out.append(new_w)
            found_w = True
        else:
            out.append(ln)
    if not found_t or not found_w:
        if text and not text.endswith("\n"):
            out.append("\n")
        if not found_t:
            out.append(new_t)
        if not found_w:
            out.append(new_w)
    return "".join(out)


def render_holdings_block(cfg: dict) -> str:
    """One advisory 'your book' line for the decision agents (Option A/B).

    Reads ``holdings_tickers`` / ``holdings_weights`` when set, else falls
    back to the risk basket (the repo's documented book + cash semantics).
    Cash is shown as the implicit remainder; names absent from the list are
    explicitly NOT held, so the PM can state "you hold no TSLA" instead of
    the conditional "if you hold it, trim". Returns "" when no book is
    configured (basket empty).
    """
    tickers = list(
        cfg.get("holdings_tickers") or cfg.get("risk_basket_tickers") or []
    )
    weights = dict(
        cfg.get("holdings_weights") or cfg.get("risk_basket_weights") or {}
    )
    if not tickers:
        return ""
    if not weights:
        weights = {s: 1.0 / len(tickers) for s in tickers}
    total_w = sum(w for w in weights.values() if w and w > 0)
    parts = ", ".join(
        f"{sym} {w * 100:.1f}%" for sym, w in sorted(weights.items(), key=lambda kv: -kv[1])
    )
    cash = max(0.0, 1.0 - total_w)
    return (
        "Computed book (advisory, from holdings/basket): "
        f"{parts}; unallocated (cash) {cash * 100:.1f}% - "
        "names not listed are not held"
    )
