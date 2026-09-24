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
- ``redundancy_screen(candidates, controls, target, ...)`` (X2): a double-
  selection LASSO over components against a control set, with an in-house L1
  solver. OFFLINE ONLY - a scheduled script consumes it, and ground rule 8
  forbids calling it from ``prepare_initial_state``, ``finalize_run`` or any
  agent tool.

No network, no LLM: the zoo is a pure catalog + evaluator, so
``scripts/factor_bench.py --zoo ...`` runs offline like Vibe's ``alpha bench``.
"""

from __future__ import annotations

import ast

import numpy as np

# The safe operator menu (whitelist). Adding an operator requires review: it
# must be pure, deterministic and reference ONLY the columns in ``records``.
_OPERATORS = {
    "ref", "delta", "mean", "std", "zscore", "rsi", "rank", "max", "min",
    "abs", "log", "sqrt", "sign", "pct_change", "rolling_corr",
}
# Data columns the zoo expressions may reference (aliases kept narrow).
_COLUMNS = {"open", "high", "low", "close", "volume", "returns", "vwap"}


def purity_gate(expr: str, extra_fields=None) -> tuple[bool, str]:
    """Whitelist-check an expression: returns (ok, reason).

    ``extra_fields`` (H2) widens the DATA-COLUMN vocabulary for one call. The
    availability-typed factors of ``factor_schema`` are not OHLCV columns, so
    the availability gate has to be able to name them when it types an
    expression; the default ``None`` leaves the zoo's vocabulary exactly
    ``_COLUMNS``, so every existing caller behaves as before.
    """
    e = str(expr or "").strip()
    if not e:
        return False, "empty expression"
    if len(e) > 400:
        return False, "expression too long"
    try:
        tree = ast.parse(e, mode="eval")
    except SyntaxError as ex:
        return False, f"invalid syntax: {ex}"
    fields = _COLUMNS if not extra_fields else (_COLUMNS | set(extra_fields))
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
        if isinstance(node, ast.Name) and node.id not in fields and node.id not in _OPERATORS:
            return False, f"unknown name '{node.id}'"
        if isinstance(node, ast.Subscript):
            return False, "subscripting not allowed (no lookahead/indexing)"
    # the ROOT call must be a single operator (a zoo alpha = one signal);
    # nested calls inside its args are composable operators, all whitelisted
    root = tree.body
    if isinstance(root, ast.Name) and root.id in fields:
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


def _zoo_reality_check(series_list: list, fwd: list, seed: int) -> dict:
    """Universe-level White RC + Hansen SPA over the bench expressions.

    Each expression's standardised signal times the forward return is its
    candidate return series and buy&hold forward return is the benchmark.
    Returns ``{"reality_check": ..., "spa": ...}`` (both None when the bench
    cannot supply two usable candidates over a common window).
    """
    from tradingagents.strategies.evaluate import (
        reality_check as _white_rc,
        spa as _hansen_spa,
    )

    valid = [(name, s) for name, s in series_list if s is not None]
    if len(valid) < 2:
        return {"reality_check": None, "spa": None}
    idx = [i for i in range(len(fwd))
           if fwd[i] is not None and all(s[i] is not None for _, s in valid)]
    if len(idx) < 2:
        return {"reality_check": None, "spa": None}
    bench = [fwd[i] for i in idx]
    cands: dict[str, list] = {}
    for k, (name, s) in enumerate(valid):
        vals = [s[i] for i in idx]
        m = sum(vals) / len(vals)
        sd = (sum((v - m) ** 2 for v in vals) / (len(vals) - 1)) ** 0.5
        if sd <= 0:
            continue
        cands[f"{name}#{k}"] = [((v - m) / sd) * bench[t] for t, v in enumerate(vals)]
    if len(cands) < 2:
        return {"reality_check": None, "spa": None}
    return {"reality_check": _white_rc(cands, bench, seed=seed),
            "spa": _hansen_spa(cands, bench, seed=seed)}


def bench_zoo(exprs: list[str], records: list[dict],
              forward_days: int = 1, n_trials: int = 1,
              walk_forward: bool = False, cpcv_folds: int = 0, *,
              reality_check: bool = False, seed: int = 0,
              trial_ledger_dir: str | None = None) -> list[dict]:
    """Rank-IC of each gated expression vs forward returns + validation
    (W2): includes out-of-sample rank IC (leading-train split), walk-forward
    across rolling train/test folds, CPCV overfit flag, and a deflated-Sharpe
    adjusted IC when ``n_trials`` > 1. never raises.

    With ``reality_check=True`` every row gains one extra ``reality_check``
    key holding the universe-level ``{"reality_check": ..., "spa": ...}``
    results (White's RC and Hansen's SPA over the bench expressions vs the
    forward-return benchmark); the default path is unchanged.

    With ``trial_ledger_dir`` set (and ``enable_trial_ledger`` on) the deflated
    IC stops trusting the caller's ``n_trials``: every evaluated candidate is
    recorded as one row in the trial ledger, N and V are read back FROM those
    rows, and each row gains ``deflated_ic_n_trials`` and
    ``deflated_ic_dispersion`` beside the number, so a published deflated IC
    carries the search it was deflated against. With the gate off the argument
    is inert and the caller-supplied path below is unchanged.
    """
    from tradingagents.strategies.evaluate import (
        cpcv_overfit_mask,
        deflated_sharpe,
        deflated_sharpe_report,
        purged_cpcv_splits,
        sharpe,
    )
    from tradingagents.strategies.signal_analysis import rank_ic
    from tradingagents.strategies.trial_ledger import (
        gate_on,
        record,
        returns_sha,
        trial_stats,
    )

    ledger_dir = trial_ledger_dir if (trial_ledger_dir is not None and gate_on()) else None
    closes = [r.get("close") for r in records]
    n = len(closes)
    first_date = str((records[0] or {}).get("date") or "") if records else ""
    last_date = str((records[-1] or {}).get("date") or "") if records else ""
    as_of = last_date
    ledger_window = (f"{first_date}..{last_date}" if (first_date or last_date)
                     else f"bars:0..{n - 1}")
    ledger_rows: list[tuple[dict, list | None]] = []

    def _fwd(i):
        j = i + forward_days
        if j < n and closes[i] and closes[j]:
            return closes[j] / closes[i] - 1.0
        return None

    out = []
    fwd_all = [_fwd(i) for i in range(n)]
    series_list: list = []
    for expr in exprs:
        series, err = evaluate_expr(expr, records)
        row = {"expr": expr, "rank_ic": None, "error": err or None,
               "oos_rank_ic": None, "wf_ic": None, "cpcv_overfit": None,
               "deflated_ic": None}
        if series is not None and err == "":
            fwd = fwd_all
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
            dr = None
            if n_trials > 1 or ledger_dir is not None:
                dr = [0.0] * n
                for i in range(n):
                    if fwd[i] is not None and series[i] is not None:
                        dr[i] = series[i] * fwd[i]
            if dr is not None and ledger_dir is None:
                row["deflated_ic"] = round(deflated_sharpe(dr, n_trials), 4)
            if dr is not None and ledger_dir is not None:
                # One immutable row per EVALUATED candidate: the ledger is what
                # supplies N and V below, so it has to see every candidate.
                record(expr, ledger_window, returns_sha(dr), sharpe(dr), as_of,
                       results_dir=ledger_dir)
                ledger_rows.append((row, dr))
        series_list.append((expr, series))
        out.append(row)
    if ledger_dir is not None and ledger_rows:
        stats = trial_stats(results_dir=ledger_dir)
        n_ledger = stats.get("n_trials")
        v_ledger = stats.get("sharpe_dispersion")
        for row, dr in ledger_rows:
            if n_ledger is None:
                # The ledger measured nothing (gate off, or the write failed):
                # the caller's count is all there is, and the row says so.
                if n_trials > 1:
                    row["deflated_ic"] = round(deflated_sharpe(dr, n_trials), 4)
                row["deflated_ic_n_trials"] = max(1, int(n_trials))
                row["deflated_ic_dispersion"] = "assumed"
                continue
            rep = deflated_sharpe_report(dr, n_trials=n_ledger,
                                         sharpe_dispersion=v_ledger)
            value = rep["value"]
            row["deflated_ic"] = round(value, 4) if isinstance(value, float) else None
            row["deflated_ic_n_trials"] = rep["n_trials"]
            row["deflated_ic_dispersion"] = rep["dispersion"]
    if reality_check:
        universe = _zoo_reality_check(series_list, fwd_all, seed)
        for row in out:
            row["reality_check"] = universe
    return out


# ---------------------------------------------------------------------------
# Redundancy screen over components (X2): double-selection LASSO, offline only
# ---------------------------------------------------------------------------
#
# 2601.06499 screens 191 short-horizon signals against 151 fundamental controls
# and keeps 17. This engine's technical score carries 39 components and the
# expression DSL can generate hundreds, and nothing asks which of them earn
# anything given the rest. This is that screen, run OFFLINE on a schedule: its
# consumption is a decision (a component that never survives becomes a
# documented component rather than a scored one), never an in-run computation.
# Ground rule 8 forbids calling it from ``prepare_initial_state``, ``finalize_run``
# or any agent tool.
#
# The L1 solver is HAND-ROLLED (coordinate descent over numpy) rather than
# ``sklearn``, which is absent and whose addition is an open owner decision -
# the conservative choice is to ship the selection half in-house, since the
# screen only needs a survivor list.

#: Theoretical LASSO penalty: ``lam = c * sd(y) * sqrt(2 log(p) / n)`` (the
#: Belloni/Chernozhukov/Hansen rate). Declared, not cross-validated: the doc
#: only needs a survivor list, and a CV fold would add a second window choice.
DEFAULT_LASSO_C = 1.1
#: Survival threshold on the post-double-selection t statistic (two-sided 5%).
DEFAULT_MIN_ABS_T = 1.96
#: Below these row counts a window cannot carry an OLS with a t statistic.
MIN_SELECTION_ROWS = 10
MIN_EVALUATION_ROWS = 5
_LASSO_MAX_ITER = 200
_LASSO_TOL = 1e-9


def _finite(value) -> bool:
    """True when ``value`` is a finite float (None/NaN -> missing, not zero)."""
    try:
        return bool(np.isfinite(float(value)))
    except (TypeError, ValueError):
        return False


def _clean_rows(target: list, columns: list, rows: list[int]) -> list[int]:
    """Rows of ``rows`` where the target and every column are finite.

    A row with a missing value is dropped, never filled - the screen measures
    over the window it can actually see and reports that count.
    """
    keep: list[int] = []
    for i in rows:
        if not _finite(target[i]):
            continue
        if any(not _finite(col[i]) for col in columns):
            continue
        keep.append(i)
    return keep


def _matrix(series: list, rows: list[int]) -> np.ndarray:
    """``(len(rows), len(series))`` float matrix, one column per named series."""
    if not series or not rows:
        return np.zeros((len(rows), len(series)), dtype=float)
    return np.asarray([[float(s[i]) for s in series] for i in rows], dtype=float)


def _fit_scale(matrix: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Column means/scales fitted on the SELECTION window (the learn/infer split).

    A degenerate scale (a constant column) becomes 1.0 rather than zero: the
    column keeps its (zero) signal instead of dividing the screen by zero.
    """
    mu = matrix.mean(axis=0)
    sd = matrix.std(axis=0, ddof=1) if matrix.shape[0] > 1 else np.ones(matrix.shape[1])
    return mu, np.where(sd > 1e-12, sd, 1.0)


def _lasso_lambda(y: np.ndarray, p: int, c: float) -> float:
    """The declared LASSO penalty for a column count ``p`` (Belloni rate)."""
    n = int(y.size)
    if n < 2 or p < 1:
        return 0.0
    sd = float(np.std(y, ddof=1))
    return float(c * sd * np.sqrt(2.0 * np.log(max(p, 2)) / n))


def _lasso_cd(X: np.ndarray, y: np.ndarray, lam: float,
              *, max_iter: int = _LASSO_MAX_ITER, tol: float = _LASSO_TOL,
              ) -> tuple[np.ndarray, float]:
    """In-house L1 selection: coordinate descent for the LASSO (no sklearn).

    Minimises ``1/(2n) ||y - Xb||^2 + lam*||b||_1``. Deterministic by
    construction - fixed iteration cap, fixed sweep order, no random restarts
    and no cross-validation. Columns are standardised by the caller so one
    ``lam`` is comparable across them. Returns ``(coef, intercept)``.
    """
    n, p = X.shape
    coef = np.zeros(p, dtype=float)
    if n == 0 or p == 0:
        return coef, 0.0
    y_mean = float(np.mean(y))
    resid = y - y_mean
    col_ss = np.sum(X * X, axis=0) / n
    for _ in range(max(1, int(max_iter))):
        delta = 0.0
        for j in range(p):
            if col_ss[j] <= 1e-12:
                continue
            old = coef[j]
            rho = float(np.dot(X[:, j], resid)) / n + old * col_ss[j]
            new = float(np.sign(rho) * max(abs(rho) - lam, 0.0)) / col_ss[j]
            if new != old:
                resid = resid - (new - old) * X[:, j]
                coef[j] = new
                delta = max(delta, abs(new - old))
        if delta < tol:
            break
    intercept = y_mean - float(np.dot(np.mean(X, axis=0), coef))
    return coef, intercept


def _lasso_selected(X: np.ndarray, v: np.ndarray, c: float) -> list[int]:
    """Indices of the columns a LASSO keeps when predicting ``v``."""
    if X.size == 0 or v.size == 0 or X.shape[1] == 0:
        return []
    coef, _ = _lasso_cd(X, v, _lasso_lambda(v, X.shape[1], c))
    return [j for j in range(X.shape[1]) if abs(float(coef[j])) > 1e-12]


def _ols(X: np.ndarray, y: np.ndarray) -> tuple[np.ndarray | None, np.ndarray | None]:
    """OLS coefficients and standard errors; ``(None, None)`` on a short/singular design.

    A design that cannot be inverted (fewer rows than columns, collinear
    columns) yields no coefficient rather than a fabricated one.
    """
    n, p = X.shape
    if n <= p or p == 0:
        return None, None
    design = np.column_stack([np.ones(n), X])
    try:
        beta, *_ = np.linalg.lstsq(design, y, rcond=None)
    except np.linalg.LinAlgError:
        return None, None
    resid = y - design @ beta
    dof = n - design.shape[1]
    if dof <= 0:
        return None, None
    sigma2 = float(resid @ resid) / dof
    try:
        xtx_inv = np.linalg.inv(design.T @ design)
    except np.linalg.LinAlgError:
        return None, None
    se = np.sqrt(np.clip(np.diag(xtx_inv) * sigma2, 0.0, None))
    return beta, se


def _post_double_selection_controls(cand: np.ndarray, ctrl: np.ndarray, j: int,
                                    y: np.ndarray, c: float) -> list[int]:
    """The controls selected for candidate ``j``'s post-double-selection design.

    The standard double selection: LASSO the outcome on the controls (A), LASSO
    the candidate on the controls (B), then regress the outcome on the candidate
    plus the controls in ``A ∪ B`` - so a candidate is judged against the
    controls that matter for either equation, not against all of them.
    """
    if ctrl.size == 0 or ctrl.shape[1] == 0:
        return []
    return sorted(set(_lasso_selected(ctrl, y, c))
                  | set(_lasso_selected(ctrl, cand[:, j], c)))


def _drop_reason(t_sel, coef_sel, t_eva, coef_eva, min_abs_t: float) -> str:
    """Why one component did not survive the screen (carried into the ledger)."""
    if t_sel is None or coef_sel is None:
        return "not measurable over the selection window (too few aligned rows)"
    if abs(t_sel) < min_abs_t:
        return (f"redundant given the control set: |t|={abs(t_sel):.2f} < "
                f"{min_abs_t:g} on the selection window")
    if coef_eva is None or coef_eva == 0.0:
        return "not measurable over the evaluation window (too few aligned rows)"
    if (coef_eva > 0) != (coef_sel > 0):
        return (f"survived the selection window but flipped sign on the "
                f"evaluation window (t_eval="
                f"{'n/a' if t_eva is None else f'{t_eva:.2f}'})")
    return "did not survive the screen"


def redundancy_screen(candidates, controls, target, *,
                      selection_window: tuple[int, int],
                      evaluation_window: tuple[int, int],
                      lasso_c: float = DEFAULT_LASSO_C,
                      min_abs_t: float = DEFAULT_MIN_ABS_T,
                      results_dir: str | None = None) -> dict:
    """Double-selection LASSO over components against a control set (X2).

    ``candidates`` and ``controls`` map a name to its series (aligned by index
    with ``target``, the forward return the screen is measured against);
    ``selection_window`` fits the screen and ``evaluation_window`` is where the
    survivor list is checked, and the two MUST be disjoint - a selection that
    overlaps its evaluation is in-sample and the paper's own warning is that
    survivors are in-sample selections. An overlap raises ``ValueError``.

    Selection is fitted on the selection window only (means/scales included) and
    applied to the evaluation window - the ``DataHandlerLP`` learn/infer split.
    A component is KEPT when the post-double-selection coefficient on the
    selection window clears ``min_abs_t`` and its evaluation-window coefficient
    keeps the same sign; otherwise it is DROPPED, and every dropped component is
    logged as one row in the H7 refusal ledger naming this screen and both
    windows.

    Deterministic: no randomness, no cross-validation, no network, and no
    in-run caller. Missing data makes a window unmeasurable, which is reported
    as ``unavailable`` with the reason and drops every candidate (rather than
    inventing a coefficient). Returns
    ``{kept, dropped, coefficients, window, selection_window, evaluation_window,
    n_selection, n_evaluation, min_abs_t, lasso_c, unavailable}``.

    The L1 solver is in-house (``_lasso_cd``): ``sklearn`` is absent and adding
    it is an open owner decision, so the conservative choice is the hand-rolled
    coordinate descent above.
    """
    sel = (int(selection_window[0]), int(selection_window[1]))
    eva = (int(evaluation_window[0]), int(evaluation_window[1]))
    if set(range(*sel)) & set(range(*eva)):
        raise ValueError(
            f"selection window {sel} overlaps evaluation window {eva}: a screen "
            "must select on one window and be checked on another"
        )
    names = sorted(candidates)
    knames = sorted(controls)
    cand = [candidates[n] for n in names]
    ctrl = [controls[k] for k in knames]
    window = f"select:{sel[0]}..{sel[1]}|eval:{eva[0]}..{eva[1]}"

    sel_rows = _clean_rows(target, cand + ctrl, list(range(*sel)))
    eva_rows = _clean_rows(target, cand + ctrl, list(range(*eva)))
    out = {
        "kept": [],
        "dropped": list(names),
        "coefficients": {n: {"selection": None, "t_selection": None,
                             "evaluation": None, "t_evaluation": None}
                         for n in names},
        "selection_window": [sel[0], sel[1]],
        "evaluation_window": [eva[0], eva[1]],
        "window": window,
        "n_selection": len(sel_rows),
        "n_evaluation": len(eva_rows),
        "min_abs_t": float(min_abs_t),
        "lasso_c": float(lasso_c),
        "unavailable": None,
    }
    if len(sel_rows) < MIN_SELECTION_ROWS or len(eva_rows) < MIN_EVALUATION_ROWS:
        out["unavailable"] = (
            f"screen unavailable: {len(sel_rows)} selection row(s) "
            f"({MIN_SELECTION_ROWS} needed) and {len(eva_rows)} evaluation row(s) "
            f"({MIN_EVALUATION_ROWS} needed); every candidate is dropped unmeasured"
        )
        _log_dropped(names, out, results_dir, reason_override=out["unavailable"])
        return out
    if not names:
        return out

    # Fit on the selection window, apply to the evaluation window (no leakage of
    # evaluation-window moments into the screen).
    y_sel = _matrix([target], sel_rows)[:, 0]
    y_eva = _matrix([target], eva_rows)[:, 0]
    mu_y, sd_y = _fit_scale(y_sel.reshape(-1, 1))
    y_sel_s = (y_sel - mu_y[0]) / sd_y[0]
    y_eva_s = (y_eva - mu_y[0]) / sd_y[0]
    cand_sel = _matrix(cand, sel_rows)
    cand_eva = _matrix(cand, eva_rows)
    ctrl_sel = _matrix(ctrl, sel_rows)
    ctrl_eva = _matrix(ctrl, eva_rows)
    mu_x, sd_x = _fit_scale(cand_sel)
    cand_sel_s = (cand_sel - mu_x) / sd_x
    cand_eva_s = (cand_eva - mu_x) / sd_x
    mu_k, sd_k = _fit_scale(ctrl_sel)
    ctrl_sel_s = (ctrl_sel - mu_k) / sd_k
    ctrl_eva_s = (ctrl_eva - mu_k) / sd_k
    c = float(lasso_c)

    kept: list[str] = []
    dropped: list[str] = []
    for j, name in enumerate(names):
        keep_idx = _post_double_selection_controls(
            cand_sel_s, ctrl_sel_s, j, y_sel_s, c)
        z_sel = (np.column_stack([cand_sel_s[:, [j]], ctrl_sel_s[:, keep_idx]])
                 if keep_idx else cand_sel_s[:, [j]])
        coef_sel = t_sel = None
        beta, se = _ols(z_sel, y_sel_s)
        # beta[0] is the intercept; the candidate is the first regressor.
        if beta is not None and se is not None and len(beta) > 1 and se[1] > 0:
            coef_sel = float(beta[1])
            t_sel = coef_sel / float(se[1])
        z_eva = (np.column_stack([cand_eva_s[:, [j]], ctrl_eva_s[:, keep_idx]])
                 if keep_idx else cand_eva_s[:, [j]])
        coef_eva = t_eva = None
        beta_e, se_e = _ols(z_eva, y_eva_s)
        if beta_e is not None and se_e is not None and len(beta_e) > 1 and se_e[1] > 0:
            coef_eva = float(beta_e[1])
            t_eva = coef_eva / float(se_e[1])
        out["coefficients"][name] = {
            "selection": coef_sel, "t_selection": t_sel,
            "evaluation": coef_eva, "t_evaluation": t_eva,
        }
        survived = (
            t_sel is not None and abs(t_sel) >= float(min_abs_t)
            and coef_eva is not None and coef_eva != 0.0
            and (coef_eva > 0) == (coef_sel > 0)
        )
        (kept if survived else dropped).append(name)
    out["kept"] = kept
    out["dropped"] = dropped
    _log_dropped(dropped, out, results_dir)
    return out


def _log_dropped(dropped: list[str], result: dict, results_dir: str | None,
                 reason_override: str | None = None) -> None:
    """One refusal-ledger row per dropped component, naming screen + windows.

    The screen's consumption is a decision, so a dropped component must be
    readable as a decision later: each row names this screen, both windows and
    the reason. Best-effort - the ledger gate being off writes nothing, and
    ``log_refusal`` never raises on IO, so a screen run cannot be broken by its
    own audit trail.
    """
    from tradingagents.strategies.refusal_ledger import log_refusal

    for name in dropped:
        coef = (result.get("coefficients") or {}).get(name) or {}
        reason = reason_override or _drop_reason(
            coef.get("t_selection"), coef.get("selection"),
            coef.get("t_evaluation"), coef.get("evaluation"),
            float(result.get("min_abs_t", DEFAULT_MIN_ABS_T)),
        )
        log_refusal(
            symbol=name,
            gate="redundancy_screen",
            reason=f"dropped by the redundancy screen over {result['window']}: {reason}",
            results_dir=results_dir,
            component=name,
            screen="redundancy_screen",
            window=result["window"],
            selection_window=result["selection_window"],
            evaluation_window=result["evaluation_window"],
        )


__all__ = ["purity_gate", "evaluate_expr", "bench_zoo", "redundancy_screen",
           "_OPERATORS", "_COLUMNS"]
