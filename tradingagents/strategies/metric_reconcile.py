"""Gather-time metric reconciliation (review: "data-quality controls").

The deterministic gatherer records one leaf per tool, but several tools can
return the SAME metric from DIFFERENT vendors (get_fundamentals Market Cap,
get_ratios Market cap, get_basic_financials marketCapitalization) with
values that disagree slightly — the TJX 2026-09-08 fundamentals report quoted
DCF 80.76 / EPS 5.81 / ROE 62.17 etc. because the analyst chose one vendor
per section and never reconciled. The post-hoc verifier catches this
(``report_verifier._internal_conflicts``); this module moves the detection to
INGEST time so the evidence block itself tells the analyst the metric is in
conflict BEFORE they reduce.

Pure and unit-testable: no IO, no LLM. The metric mapping is an explicit,
conservative table (only tools we know produce the same metric), so a new or
unknown tool never gets merged accidentally; a metric with one vendor is
quiet (no conflict, no span). Values are read from the leaf line that NAMES
the metric (``TOOL_VALUE_RE``), never from the first number in the leaf:
QQQI 2026-09-13 quoted a phantom ``market_cap: VALUES CONFLICT range=10 ..
2026`` because the first-number extractor read a note date (2026) and a
volume label (10DayAverageTradingVolume) in a leaf set that carried no market
cap at all.
"""

from __future__ import annotations

import re

# Tolerance: two values of the same metric are "the same" when within 1%
# relative (matches the internal-conflict verifier's threshold).
MATCH_TOLERANCE = 0.01

# Tool-name -> canonical metric id. MULTIPLE tools that report the SAME
# underlying metric map to ONE key so their (possibly vendor-conflicting)
# values are compared: get_fundamentals.Market Cap, get_ratios.Market cap and
# get_basic_financials.marketCapitalization all feed "market_cap"; the
# analyst then sees the conflict at ingest. A tool NOT listed (or a tool that
# returns a genuinely different measure, e.g. epsTTM vs epsAnnual) is never
# merged — conservative, so a new tool never gets bucketed accidentally.
TOOL_METRIC_MAP: dict[str, str] = {
    # valuation
    "get_dcf_valuation": "dcf",
    "get_fcf_yield": "fcf_yield",
    "get_value_floors": "value_floors",
    "get_ratios": "market_cap",
    "get_basic_financials": "market_cap",
    "get_fundamentals": "market_cap",
    # balance / capital
    "get_balance_sheet": "balance_sheet",
    "get_cashflow": "cash_flow",
    "get_income_statement": "income_statement",
    # market
    "get_market_snapshot": "market_snapshot",
    "get_verified_market_snapshot": "market_snapshot",
}

# Tool-name -> the regex that pulls THIS tool's reconcildable value from
# the line that labels it. Label-anchored on purpose: a leaf is a multi-line
# document (header, note date, dozens of unrelated figures), so "the first
# number in the leaf" is an artifact generator, not an extractor. A tool NOT
# in this table has no single scalar (the statement CSVs are tabular) and
# contributes no value - it can therefore never manufacture a conflict.
TOOL_VALUE_RE: dict[str, re.Pattern] = {
    # get_fundamentals: "Market Cap: 99,105,693,696"
    "get_fundamentals": re.compile(r"(?im)^\s*Market\s*Cap\s*:\s*\$?\s*(\d[\d,]*(?:\.\d+)?)"),
    # get_ratios: "- Market cap: 102,260,850,000" ("n/a" yields no match)
    "get_ratios": re.compile(r"(?im)^\s*-\s*Market\s*cap\s*:\s*\$?\s*(\d[\d,]*(?:\.\d+)?)"),
    # get_basic_financials: "marketCapitalization: 3659011800000.0" (+ optional
    # "(vendor, basis unknown)" qualifier)
    "get_basic_financials": re.compile(
        r"(?im)^\s*marketCapitalization[^:\n]{0,40}:\s*\$?\s*(\d[\d,]*(?:\.\d+)?)"
    ),
    # get_dcf_valuation: "dcf adbe: fair_value=278.71 ev=..."
    "get_dcf_valuation": re.compile(r"(?i)\bfair_value\s*=\s*\$?\s*(\d[\d,]*(?:\.\d+)?)"),
    # get_fcf_yield: "fcf yield adbe: 10.37% (floor-pass); fcf=..."
    "get_fcf_yield": re.compile(r"(?i)\bfcf\s*yield[^:\n]{0,40}:\s*\$?\s*(\d[\d,]*(?:\.\d+)?)"),
    # get_value_floors: "value floors adbe (price 248.80999755859372):"
    "get_value_floors": re.compile(r"(?i)\(\s*price\s+(\d[\d,]*(?:\.\d+)?)"),
    # get_market_snapshot: "- Last: 250.27 | O 251.81 H 255 L 247.19 ..."
    "get_market_snapshot": re.compile(r"(?im)^\s*-\s*Last\s*:\s*\$?\s*(\d[\d,]*(?:\.\d+)?)"),
    # get_verified_market_snapshot: "| Close | 248.81 |" in the OHLCV table
    "get_verified_market_snapshot": re.compile(
        r"(?im)^\s*\|\s*Close\s*\|\s*\$?\s*(\d[\d,]*(?:\.\d+)?)"
    ),
}

# Debt/equity extraction: D/E appears in different shapes across tools -
# get_fundamentals "Debt to Equity: 5.62" (raw vendor), get_ratios "D/E: 0.06"
# (computed), get_balance_sheet_health "d_e=0.0552". The ARM 2026-09-09 loop
# flagged 5.62 vs 0.055 as a real conflict the one-value-per-tool extractor
# cannot see (it grabs the FIRST number in the whole leaf, e.g. market cap).
_DE_RE = re.compile(
    r"(?:debt\s*to\s*equity|d\s*/\s*e|\bd_e\b|debt[-\s/]equity)"
    r"[^\d-]{0,8}(-?[\d.,]+)",
    re.IGNORECASE,
)

# Tools whose leaves carry a D/E figure (raw vendor / computed / health row).
_DE_TOOLS = {"get_fundamentals", "get_ratios", "get_balance_sheet_health"}


def extract_de_value(content: str) -> float | None:
    """The D/E value in a leaf (None when absent / unparseable)."""
    if not content:
        return None
    m = _DE_RE.search(content)
    if not m:
        return None
    try:
        return float(m.group(1).replace(",", ""))
    except ValueError:
        return None


def extract_metric_value(tool: str, content: str) -> float | None:
    """The value this leaf LABELS as the tool's reconcildable metric.

    None when the tool has no scalar label contract (statement CSVs) or when
    the leaf does not carry the labelled figure at all - e.g. an ETF's
    ``get_fundamentals`` has no ``Market Cap`` row. There is deliberately no
    fallback to an unlabelled number.
    """
    rx = TOOL_VALUE_RE.get(str(tool or "").strip())
    if not rx or not content:
        return None
    m = rx.search(content)
    if not m:
        return None
    try:
        return float(m.group(1).replace(",", ""))
    except ValueError:
        return None


def metric_for_tool(tool: str) -> str | None:
    """Canonical metric id for a tool name (None = not reconcildable)."""
    return TOOL_METRIC_MAP.get(str(tool or "").strip())


def reconcile_metrics(
    leaves: list[dict],
    tolerance: float = MATCH_TOLERANCE,
) -> dict[str, dict]:
    """Group leaves by metric; mark CONFLICT when values differ > tolerance.

    ``leaves``: list of dicts with at least ``tool`` and ``content`` (the
    persisted leaf shape). Returns ``{metric_id: {values: [...], span:
    (lo,hi)|None, conflict: bool, vendors: [tool_name,...], labelled: bool}}``.
    A value the leaf does not label is omitted from ``values`` but the tool
    still counts toward ``vendors`` (so a vendor that returned no data doesn't
    hide a conflict between two others); ``labelled`` records whether any
    vendor for the metric could have carried a value at all.
    """
    buckets: dict[str, dict] = {}
    for leaf in leaves or []:
        if not isinstance(leaf, dict):
            continue
        tool = str(leaf.get("tool") or "")
        content = str(leaf.get("content") or "")
        # debt/equity: a leaf may carry BOTH the tool's primary metric and a
        # D/E figure (get_fundamentals / get_ratios) - bucket the D/E value
        # under its own metric so a raw-vs-computed conflict (ARM 5.62 vs
        # 0.055) is surfaced, not hidden by the first-number extractor.
        if tool in _DE_TOOLS:
            de_v = extract_de_value(content)
            if de_v is not None:
                de_bucket = buckets.setdefault(
                    "debt_to_equity",
                    {
                        "values": [],
                        "span": None,
                        "conflict": False,
                        "vendors": [],
                        "labelled": True,
                    },
                )
                de_bucket["vendors"].append(tool)
                de_bucket["values"].append(de_v)
        metric = metric_for_tool(tool)
        if not metric:
            continue
        bucket = buckets.setdefault(
            metric,
            {
                "values": [],
                "span": None,
                "conflict": False,
                "vendors": [],
                "labelled": False,
            },
        )
        bucket["vendors"].append(tool)
        if tool in TOOL_VALUE_RE:
            bucket["labelled"] = True
        v = extract_metric_value(tool, content)
        if v is not None:
            bucket["values"].append(v)

    out: dict[str, dict] = {}
    for metric, bucket in buckets.items():
        vals = bucket["values"]
        distinct: list[float] = []
        for v in vals:
            close = next(
                (d for d in distinct if abs(d - v) / max(abs(d), abs(v), 1e-9) <= tolerance),
                None,
            )
            if close is None:
                distinct.append(v)
        conflict = len(distinct) >= 2
        span = (min(distinct), max(distinct)) if distinct else None
        out[metric] = {
            "values": sorted(vals),
            "span": span,
            "conflict": conflict,
            "vendors": sorted(set(bucket["vendors"])),
            "labelled": bool(bucket.get("labelled")),
        }
    return out


def render_reconcile(reconciled: dict[str, dict]) -> str:
    """Render the reconcile line(s) for the evidence block.

    Only conflicted metrics produce a line (a single vendor or a consistent
    multi-vendor metric is NOT noise - it's fine). The line tells the analyst
    the metric is conflicted and to treat it as a range, weighted by vendor
    reliability, never pick one silently.

    A metric whose vendors are all silent ON THE LABELLED VALUE gets an
    explicit "no value in evidence" line instead: staying quiet there invites
    the analyst to re-derive the figure from unrelated numbers in the leaves
    (QQQI 2026-09-13 quoted an AUM range that no leaf ever contained).
    """
    lines: list[str] = []
    for metric in sorted(reconciled):
        b = reconciled[metric]
        vendors = ", ".join(sorted(b["vendors"]))
        if not b["conflict"]:
            # Only multi-vendor metrics are called out: a single-vendor
            # metric with no value has nothing to reconcile (its leaf already
            # says unavailable), while the analyst reading a two-vendor metric
            # expects a comparison and would otherwise re-derive one.
            if b.get("labelled") and not b["values"] and len(b["vendors"]) >= 2:
                lines.append(
                    f"- metric {metric}: NO VALUE IN EVIDENCE (vendors=[{vendors}] carry "
                    f"no labelled {metric} figure) — report it unavailable; do NOT quote "
                    "a single value or a range"
                )
            continue
        span = b["span"]
        shown = (
            f"{span[0]:.4g} .. {span[1]:.4g}"
            if span is not None
            else "n/a"
        )
        lines.append(
            f"- metric {metric}: VALUES CONFLICT range={shown} vendors=[{vendors}] — "
            "treat as a range / weight by vendor reliability; do NOT quote a single value"
        )
    return "\n".join(lines) if lines else ""


__all__ = [
    "MATCH_TOLERANCE",
    "TOOL_METRIC_MAP",
    "TOOL_VALUE_RE",
    "metric_for_tool",
    "extract_metric_value",
    "extract_de_value",
    "reconcile_metrics",
    "render_reconcile",
]
