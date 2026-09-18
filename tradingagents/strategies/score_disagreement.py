"""The quant / LLM risk-disagreement detector (WP-12 `P12-9`).

`docs/scores/ResearchLayerWiring.md` §5. The owner's proposal — flag when the
LLM's risk read contradicts `RiskScore` — built **in its weak form**, which is the
form he asked for:

* **Where.** A deterministic post-debate check over material the run already
  produced: `RiskScore`'s band (from the score snapshot) against the risk debate's
  own words (`structured_risk_state` when the structured path ran, else the PM's
  `risk_debate_state` verdict and histories). **No new producer** — both sides
  already exist.
* **What it emits.** A flag carrying both values and the reason. It **never**
  changes a score, a rating, a size or a gate.
* **Why not the strong form.** The LLM must not override the score, and the
  disagreement is *valuable*: *"Quant `35`, LLM assessment favourable, required
  review: identify the evidence causing disagreement"* is worth more than either
  number alone. A detector that suppressed the LLM's read or moved the score
  toward it would destroy the measurement layer it exists to protect.

**The LLM side is read with `RiskScore`'s own band vocabulary**, not a second
invention: the debate is scanned for the band words the engine itself uses, and
the stance is the most frequently named one. When the debate names no band at all,
the stance is **undetermined** and no flag is produced — with that reason recorded.
A guess would be a manufactured disagreement, which is worse than none.

**Only opposite stances are a contradiction.** A `moderate` on either side is a
difference of degree, not a contradiction, so it does not fire; the values are
still reported.
"""

from __future__ import annotations

import re
from collections import Counter

__all__ = [
    "BAND_STANCE",
    "llm_risk_stance",
    "risk_band_stance",
    "risk_disagreement",
]

#: `RiskScore` is INVERTED (100 = low risk), so its bands read as stances.
BAND_STANCE: dict[str, str] = {
    "low risk": "favourable",
    "contained": "favourable",
    "moderate": "neutral",
    "elevated": "neutral",
    "high risk": "unfavourable",
    "severe risk": "unfavourable",
    # the bare band words, for prose that omits "risk"
    "severe": "unfavourable",
    "high": "unfavourable",
}

#: Longest-first alternation, so "high risk" never counts as "high" as well.
_PHRASE_RE = re.compile(
    "|".join(re.escape(p) for p in sorted(BAND_STANCE, key=len, reverse=True)),
    re.IGNORECASE,
)

_OPPOSITE = {"favourable": "unfavourable", "unfavourable": "favourable"}


def risk_band_stance(band: str | None) -> str | None:
    """`RiskScore`'s band word -> a stance, or ``None`` when there is no band."""
    if not band:
        return None
    return BAND_STANCE.get(str(band).strip().lower())


def llm_risk_stance(text: str) -> tuple[str | None, dict]:
    """The risk debate's own words -> a stance, or ``None`` when it does not say.

    Returns ``(stance, counts)`` where ``counts`` is ``{band_phrase: n}``, so a
    reader can see what the classification was made from rather than trusting it.
    A tie between stances is undetermined: the debate did not settle on one.
    """
    counts: Counter = Counter()
    for match in _PHRASE_RE.finditer(str(text or "")):
        counts[match.group(0).strip().lower()] += 1
    if not counts:
        return None, {}
    by_stance: Counter = Counter()
    for phrase, n in counts.items():
        by_stance[BAND_STANCE[phrase]] += n
    top = by_stance.most_common()
    if len(top) > 1 and top[0][1] == top[1][1]:
        return None, dict(counts)
    return top[0][0], dict(counts)


def _risk_debate_text(state: dict | None) -> str:
    """Everything the risk side of the run already said, in one string.

    **The structured path when it ran, the legacy verdict when it did not** —
    §5's "or", not both. Concatenating them would let two disagreeing transcripts
    tie the classifier into `undetermined` on a run where one side clearly spoke.
    No new producer, no new call.
    """
    st = state or {}
    structured = st.get("structured_risk_state")
    if isinstance(structured, dict) and structured:
        parts: list[str] = []
        for key in ("rounds", "claim_ledger_md", "judge_decision"):
            value = structured.get(key)
            if value:
                parts.append(value if isinstance(value, str) else str(value))
        if parts:
            return "\n".join(parts)
    debate = st.get("risk_debate_state")
    if isinstance(debate, dict):
        parts = []
        for key in (
            "judge_decision",
            "history",
            "aggressive_history",
            "conservative_history",
            "neutral_history",
        ):
            value = debate.get(key)
            if value:
                parts.append(str(value))
        return "\n".join(parts)
    return ""


def risk_disagreement(snapshot: dict | None, state: dict | None) -> dict:
    """Compare the quant risk read against the debate's, and say what happened.

    Returns ``{"flag", "reason", "quant_band", "quant_stance", "llm_stance",
    "llm_bands"}``. ``flag`` is True only on an **opposite** pair: the LLM's read
    favourable while `RiskScore` says unfavourable, or the reverse. Every other
    outcome carries a reason, so "they agree" is distinguishable from "one side
    could not be read".
    """
    band = ((snapshot or {}).get("engines") or {}).get("risk", {}).get("band")
    quant = risk_band_stance(band)
    llm, counts = llm_risk_stance(_risk_debate_text(state))
    out: dict = {
        "flag": False,
        "reason": None,
        "quant_band": band,
        "quant_stance": quant,
        "llm_stance": llm,
        "llm_bands": counts,
    }
    if quant is None:
        out["reason"] = "RiskScore produced no band for this run"
        return out
    if llm is None:
        out["reason"] = (
            "the risk debate named no risk band, so there is nothing to compare"
        )
        return out
    if quant == llm:
        out["reason"] = f"both sides read {quant}"
        return out
    if _OPPOSITE.get(quant) == llm:
        out["flag"] = True
        out["reason"] = (
            f"quant {band}, debate reads {llm}: identify the evidence causing "
            "the disagreement"
        )
        return out
    out["reason"] = f"quant {quant} against a {llm} read is a difference of degree"
    return out
