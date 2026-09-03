"""Bounded expression evaluator + AST purity gate + alpha-zoo bench (Vibe-Trading alpha zoo, P2-6).

The factor-expression DSL (``factor_expressions``) evaluates a fixed operator
menu (ref/delta/mean/std/zscore/rsi/rank/... + Alpha158 feature names), not
arbitrary Python — so a "purity gate" is a static check that a proposed
expression is *composed entirely of the safe operator menu + literals + the
data columns*, with no attribute access, imports, calls to unknown names,
subscripts on the result, or lookahead references.

- ``purity_gate(expr)`` -> (ok, reason): rejects anything outside the menu.
- ``evaluate_expr(expr, records, meta)`` -> (series|None, error): deterministic
  evaluation over a sequence of OHLCV-ish dicts (never fills; missing values
  stay None). ONE named operator per expression (a zoo alpha = one signal);
  Alpha158 subset names resolve via ``factor_expressions.alpha158_subset``.
- ``bench_zoo(expr, records, forward_days)``: rank-IC of the expr vs forward
  returns (uses the rank_ic from signal_analysis) + a list of expressions.

No network, no LLM: the zoo is a pure catalog + evaluator, so
``scripts/factor_bench.py --zoo ...`` runs offline like Vibe's ``alpha bench``.
"""

from __future__ import annotations

import ast

# The safe operator menu (whitelist). Adding an operator requires review: it
# must be pure, deterministic and reference ONLY the columns in ``records``.
_OPERATORS = {
    "ref", "delta", "mean", "std", "zscore", "rsi", "rank", "max", "min",
    "abs", "log", "sqrt", "sign", "pct_change", "rolling_corr",
}
# Data columns the zoo expressions may reference (aliases kept narrow).
_COLUMNS = {"open", "high", "low", "close", "volume", "returns", "vwap"}


def purity_gate(expr: str) -> tuple[bool, str]:
    """Whitelist-check an expression: returns (ok, reason)."""
    e = str(expr or "").strip()
    if not e:
        return False, "empty expression"
    if len(e) > 400:
        return False, "expression too long"
    try:
        tree = ast.parse(e, mode="eval")
    except SyntaxError as ex:
        return False, f"invalid syntax: {ex}"
    for node in ast.walk(tree):
        if isinstance(node, ast.Attribute):
            return False, f"attribute access not allowed: {ast.unparse(node)}"
        if isinstance(node, ast.Call):
            name = None
            if isinstance(node.func, ast.Name):
                name = node.func.id
            elif isinstance(node.func, ast.Attribute):
                return False, "attribute call not allowed"
            if name not in _OPERATORS:
                return False, f"unknown operator '{name}' (not in the safe menu)"
        if isinstance(node, ast.Name) and node.id not in _COLUMNS and node.id not in _OPERATORS:
            return False, f"unknown name '{node.id}'"
        if isinstance(node, ast.Subscript):
            return False, "subscripting not allowed (no lookahead/indexing)"
    # the ROOT call must be a single operator (a zoo alpha = one signal);
    # nested calls inside its args are composable operators, all whitelisted
    root = tree.body
    if isinstance(root, ast.Name) and root.id in _COLUMNS:
        return True, ""  # a bare column is a valid raw signal
    if not isinstance(root, ast.Call):
        return False, "a zoo alpha must be one operator expression or a column"
    return True, ""


# Minimal AST evaluator over the safe menu (each operator applied to a plain
# numeric list; None passthrough; no side effects). Kept tiny + hermetic.
def _op(name: str, args: list) -> list:
    values = args[0] if args else []
    if name == "ref":
        k = int(args[1]) if len(args) > 1 and isinstance(args[1], int) else 1
        return [None if i < k else values[i - k] for i in range(len(values))]
    if name == "delta":
        k = int(args[1]) if len(args) > 1 and isinstance(args[1], int) else 1
        return [None if i < k or values[i] is None or values[i - k] is None
                else values[i] - values[i - k] for i in range(len(values))]
    if name == "mean":
        k = int(args[1]) if len(args) > 1 and isinstance(args[1], int) else 5
        out = []
        for i in range(len(values)):
            w = [v for v in values[max(0, i - k + 1): i + 1] if v is not None]
            out.append(sum(w) / len(w) if w else None)
        return out
    if name == "std":
        k = int(args[1]) if len(args) > 1 and isinstance(args[1], int) else 5
        out = []
        for i in range(len(values)):
            w = [v for v in values[max(0, i - k + 1): i + 1] if v is not None]
            if len(w) >= 2:
                m = sum(w) / len(w)
                out.append((sum((x - m) ** 2 for x in w) / (len(w) - 1)) ** 0.5)
            else:
                out.append(None)
        return out
    if name == "zscore":
        k = int(args[1]) if len(args) > 1 and isinstance(args[1], int) else 5
        out = []
        for i in range(len(values)):
            w = [v for v in values[max(0, i - k + 1): i + 1] if v is not None]
            if len(w) >= 2:
                m = sum(w) / len(w)
                s = (sum((x - m) ** 2 for x in w) / (len(w) - 1)) ** 0.5
                out.append((values[i] - m) / s if s > 0 else None)
            else:
                out.append(None)
        return out
    if name == "abs":
        return [None if v is None else abs(v) for v in values]
    if name == "sign":
        return [None if v is None else (1 if v > 0 else (-1 if v < 0 else 0))
                for v in values]
    if name == "log":
        import math
        return [None if v is None or v <= 0 else math.log(v) for v in values]
    if name == "sqrt":
        import math
        return [None if v is None or v < 0 else math.sqrt(v) for v in values]
    if name == "max":
        return [None if v is None else max(v, 0.0) for v in values]
    if name == "min":
        return [None if v is None else min(v, 0.0) for v in values]
    if name == "rank":
        order = sorted((v, i) for i, v in enumerate(values) if v is not None)
        ranks = [None] * len(values)
        for pos, (_, i) in enumerate(order):
            ranks[i] = float(pos + 1)
        return ranks
    if name == "pct_change":
        k = int(args[1]) if len(args) > 1 and isinstance(args[1], int) else 1
        return [None if i < k or values[i - k] in (None, 0) or values[i] is None
                else values[i] / values[i - k] - 1.0 for i in range(len(values))]
    if name == "rolling_corr":
        k = int(args[1]) if len(args) > 1 and isinstance(args[1], int) else 5
        b = args[2] if len(args) > 2 else values
        out = []
        for i in range(len(values)):
            w1 = [values[j] for j in range(max(0, i - k + 1), i + 1) if values[j] is not None and b[j] is not None]
            w2 = [b[j] for j in range(max(0, i - k + 1), i + 1) if values[j] is not None and b[j] is not None]
            if len(w1) >= 2 and len(set(w1)) > 1 and len(set(w2)) > 1:
                m1, m2 = sum(w1) / len(w1), sum(w2) / len(w2)
                num = sum((x - m1) * (y - m2) for x, y in zip(w1, w2, strict=False))
                d1 = (sum((x - m1) ** 2 for x in w1) ** 0.5)
                d2 = (sum((y - m2) ** 2 for y in w2) ** 0.5)
                out.append(num / (d1 * d2) if d1 and d2 else None)
            else:
                out.append(None)
        return out
    return [None] * len(values)


def _eval_node(node, series: dict) -> list:
    """Evaluate a gated AST node against the per-column series dict."""
    if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)):
        return [float(node.value)] * max((len(next(iter(series.values()), []))), 1)
    if isinstance(node, ast.Name):
        return series.get(node.id, [None] * len(series.get("close", [])))
    if isinstance(node, ast.Call):
        name = node.func.id
        arg_series = [_eval_node(a, series) for a in node.args]
        # first arg that is a real series is the primary; numeric args pass as ints
        ints = [int(a if isinstance(a, (int, float)) else 0)
                for a in node.args
                if isinstance(a, (int, float))]
        out = _op(name, arg_series + ints or [arg_series[0] if arg_series else []])
        return out
    return [None] * len(series.get("close", []))


def evaluate_expr(expr: str, records: list[dict]) -> tuple[list | None, str]:
    """Evaluate one gated expression over records; (series, error).

    ``records`` is a list of OHLCV-ish dicts in date order. Only the declared
    ``_OPERATORS`` are reachable; anything ungated returns (None, reason).
    """
    ok, reason = purity_gate(expr)
    if not ok:
        return None, reason
    e = expr.strip()
    # Alpha158 subset names (the zoo's named-feature path)
    try:
        from tradingagents.strategies.factor_expressions import alpha158_subset

        feat = alpha158_subset(
            {"close": [r.get("close") for r in records],
             "open": [r.get("open") for r in records],
             "high": [r.get("high") for r in records],
             "low": [r.get("low") for r in records],
             "volume": [r.get("volume") for r in records]},
        )
        if e in feat:
            return feat[e], ""
    except Exception:  # noqa: BLE001 - named-feature fallback is best-effort
        pass
    series = {c: [r.get(c) for r in records] for c in _COLUMNS}
    try:
        tree = ast.parse(e, mode="eval")
        return _eval_node(tree.body, series), ""
    except Exception as exc:  # noqa: BLE001 - evaluation is bounded
        return None, f"evaluation failed: {exc}"


def bench_zoo(exprs: list[str], records: list[dict],
              forward_days: int = 1, n_trials: int = 1,
              walk_forward: bool = False, cpcv_folds: int = 0) -> list[dict]:
    """Rank-IC of each gated expression vs forward returns + validation
    (W2): includes out-of-sample rank IC (leading-train split), walk-forward
    across rolling train/test folds, CPCV overfit flag, and a deflated-Sharpe
    adjusted IC when ``n_trials`` > 1. never raises."""
    from tradingagents.strategies.evaluate import (
        cpcv_overfit_mask,
        deflated_sharpe,
        purged_cpcv_splits,
    )
    from tradingagents.strategies.signal_analysis import rank_ic

    closes = [r.get("close") for r in records]
    n = len(closes)

    def _fwd(i):
        j = i + forward_days
        if j < n and closes[i] and closes[j]:
            return closes[j] / closes[i] - 1.0
        return None

    out = []
    for expr in exprs:
        series, err = evaluate_expr(expr, records)
        row = {"expr": expr, "rank_ic": None, "error": err or None,
               "oos_rank_ic": None, "wf_ic": None, "cpcv_overfit": None,
               "deflated_ic": None}
        if series is not None and err == "":
            fwd = [_fwd(i) for i in range(n)]
            ic = rank_ic(series, fwd)
            row["rank_ic"] = ic
            # OOS rank IC on the trailing 30% (W2-4)
            sig_o, fwd_o = [], []
            cut = int(n * 0.7)
            sig_o, fwd_o = series[cut:], fwd[cut:]
            if sig_o and any(v is not None for v in fwd_o):
                row["oos_rank_ic"] = rank_ic(sig_o, fwd_o)
            # walk-forward mean IC (W2-3) over index folds
            if walk_forward and n >= 60:
                ics = []
                for s0 in range(0, n - 40, 20):
                    t0 = s0 + 40
                    sig_t = [series[i] for i in range(t0, min(n, t0 + 20))]
                    fwd_t = [fwd[i] for i in range(t0, min(n, t0 + 20))]
                    fri = rank_ic(sig_t, fwd_t)
                    if fri is not None:
                        ics.append(fri)
                if ics:
                    row["wf_ic"] = round(sum(ics) / len(ics), 4)
            # CPCV overfit mask (W2-2)
            if cpcv_folds >= 2 and n >= 40:
                ipcs, oopcs = [], []
                for train, test in purged_cpcv_splits(n, n_splits=cpcv_folds, embargo=forward_days):
                    ipc = rank_ic([series[i] for i in train], [fwd[i] for i in train])
                    opc = rank_ic([series[i] for i in test], [fwd[i] for i in test])
                    if ipc is not None:
                        ipcs.append(ipc)
                    if opc is not None:
                        oopcs.append(opc)
                if ipcs:
                    row["cpcv_overfit"] = cpcv_overfit_mask(ipcs, oopcs)
            # deflated IC (W2-1): penalize multi-trial selection on the
            # one-factor-per-expr directional series proxy.
            if n_trials > 1:
                dr = [0.0] * n
                for i in range(n):
                    if fwd[i] is not None and series[i] is not None:
                        dr[i] = series[i] * fwd[i]
                row["deflated_ic"] = round(deflated_sharpe(dr, n_trials), 4)
        out.append(row)
    return out


__all__ = ["purity_gate", "evaluate_expr", "bench_zoo", "_OPERATORS", "_COLUMNS"]
