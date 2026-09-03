"""Thesis-vs-evidence matrix (W3-6) + prompt-injection hardening (W3-8) +
complexity report (W4-8).

- ``thesis_evidence_matrix`` — turn structured claims + measured evidence
  into the ChatGPT "Revenues accelerating | +18% YoY | Strong | None |
  Confirmed" table: a computed matrix from the claim ledger + computed
  metrics, NOT an LLM narrative.
- ``detect_injection`` — a deterministic heuristic for instruction-injected
  payloads in ingested text (news/social/web): flags meta-instruction
  patterns ("ignore previous", "you are now", system-role spoofs) so an
  analyst prompt can strip/flag them (W3-8). Conservative: only flags
  explicit phrasing, never a false-alarm on normal prose.
- ``complexity_report`` — per-module LOC count + rough dependency fan-in
  (imports), the W4-8 periodic maintenance-tax report.
"""

from __future__ import annotations

import ast
import re
from pathlib import Path

# Injection markers (W3-8). Conservative literal hints only.
_INJECTION_PATTERNS = (
    re.compile(r"ignore\s+(all\s+)?(previous|prior)\s+(instructions|prompts)", re.I),
    re.compile(r"you\s+are\s+now\s+(?:a|an|the)\s+\w+\s*(?:assistant|agent|system|bot)", re.I),
    re.compile(r"system\s*(?:role|prompt|message)\s*[:=]", re.I),
    re.compile(r"forget\s+everything\s+(above|previously)", re.I),
    re.compile(r"override\s+(all\s+)?(previous|instructions)", re.I),
    re.compile(r"print\s+(?:the\s+)?(?:password|secret|key)\b", re.I),
)


def detect_injection(text: str) -> dict:
    """Scan ingested text for instruction-injection hints (W3-8).

    Returns {injected: bool, matches: [phrase, ...]}. Conservative: only
    explicit meta-instruction phrasing triggers; normal financial prose does
    not.
    """
    t = str(text or "")
    hits = [p.pattern for p in _INJECTION_PATTERNS if p.search(t)]
    return {"injected": bool(hits), "matches": hits}


def thesis_evidence_matrix(claims: list[dict], evidence: dict) -> list[dict]:
    """W3-6: render claims vs measured evidence into the matrix.

    Each claim: {thesis, metric, direction ("up"|"down"|"level"), target}
    ``evidence``: {metric: current_value}. Strength: Strong when the measured
    value moved the claimed direction (or matches a level) by >5%; Medium
    when within 5%; otherwise Contradicted. Status: Confirmed / Mixed /
    Contradicted. Unmeasured metric -> strength None, status "unmeasured"
    (honest, never assumed).
    """
    out = []
    for c in (claims or []):
        thesis = str(c.get("thesis") or "")
        metric = str(c.get("metric") or "")
        ev = evidence.get(metric)
        if ev is None:
            out.append({"thesis": thesis, "metric": metric, "evidence": None,
                        "strength": None, "status": "unmeasured"})
            continue
        direction = str(c.get("direction") or "level")
        target = c.get("target")
        try:
            ev = float(ev)
            target = float(target) if target is not None else None
        except (TypeError, ValueError):
            out.append({"thesis": thesis, "metric": metric, "evidence": ev,
                        "strength": None, "status": "unmeasured"})
            continue
        if direction == "up":
            ok = target is not None and ev >= target
            near = target is not None and abs(ev - target) / abs(target) <= 0.05
        elif direction == "down":
            ok = target is not None and ev <= target
            near = target is not None and abs(ev - target) / abs(target) <= 0.05
        else:  # level
            ok = target is not None and abs(ev - target) / abs(target) <= 0.05
            near = ok
        if ok:
            strength, status = "Strong", "Confirmed"
        elif near:
            strength, status = "Medium", "Mixed"
        else:
            strength, status = "Weak", "Contradicted"
        out.append({"thesis": thesis, "metric": metric, "evidence": ev,
                    "strength": strength, "status": status})
    return out


def complexity_report(root: Path, top: int = 12) -> dict:
    """W4-8: per-module LOC + import fan-in (dependency count) under ``root``.

    Returns {modules: [{path, loc, imports}], total_loc, module_count}.
    Deterministic + fast (AST-level; skips __pycache__).
    """
    modules = []
    total = 0
    for p in sorted(root.rglob("*.py")):
        if "__pycache__" in str(p):
            continue
        try:
            src = p.read_text(encoding="utf-8", errors="ignore")
            tree = ast.parse(src)
        except Exception:  # noqa: BLE001 - counting is advisory
            continue
        imports = 0
        for n in ast.walk(tree):
            if isinstance(n, (ast.Import, ast.ImportFrom)):
                imports += 1
        loc = src.count("\n")
        total += loc
        modules.append({"path": str(p.relative_to(root)), "loc": loc,
                        "imports": imports})
    modules.sort(key=lambda m: -m["loc"])
    return {"modules": modules[:top], "total_loc": total,
            "module_count": len(modules),
            "biggest": modules[0] if modules else None}


__all__ = ["detect_injection", "thesis_evidence_matrix", "complexity_report",
           "_INJECTION_PATTERNS"]
