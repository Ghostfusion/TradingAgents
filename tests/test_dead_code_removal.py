"""Phase-D dead-code removals — surviving-behaviour pins.

Every test drives the path that SURVIVES a deletion, so reinstating a removed
shim/alias/helper (or losing a deduplicated shared helper) fails here.
"""

from __future__ import annotations

import importlib
import importlib.util
from unittest import mock

import pandas as pd
import pytest

from tradingagents.agents.utils import analysis_tools as T, value_dip_tools as V

pytestmark = pytest.mark.timeout(120)


def _ohlcv_df(closes: list[float]) -> pd.DataFrame:
    """A frame shaped like the ``_load_ohlcv_df`` seam's real return."""
    dates = pd.date_range("2025-01-01", periods=len(closes), freq="D").strftime("%Y-%m-%d")
    return pd.DataFrame(
        {
            "Date": dates,
            "Open": closes,
            "High": [c + 1.0 for c in closes],
            "Low": [c - 1.0 for c in closes],
            "Close": closes,
            "Volume": [1_000_000.0] * len(closes),
        }
    )


def _dip_closes(n: int = 60) -> list[float]:
    """The sustained-dip series the value-dip tool tests use (oversold)."""
    closes = []
    px = 140.0
    for i in range(n):
        px += -1.2 if i % 5 != 2 else 0.3
        closes.append(px)
    return closes


# ---------------------------------------------------------------------------
# Deprecated social_media_analyst shim + create_social_media_analyst alias
# ---------------------------------------------------------------------------


def test_agents_package_exports_only_the_live_sentiment_factory():
    agents = importlib.import_module("tradingagents.agents")
    assert callable(agents.create_sentiment_analyst)
    assert not hasattr(agents, "create_social_media_analyst")


def test_sentiment_analyst_module_has_no_deprecated_alias():
    mod = importlib.import_module("tradingagents.agents.analysts.sentiment_analyst")
    assert callable(mod.create_sentiment_analyst)
    assert not hasattr(mod, "create_social_media_analyst")


def test_social_media_analyst_shim_module_is_gone():
    assert (
        importlib.util.find_spec("tradingagents.agents.analysts.social_media_analyst")
        is None
    )


# ---------------------------------------------------------------------------
# Dead per-role debate tool surfaces (role_tools + the phantom tool names)
# ---------------------------------------------------------------------------


def test_debate_roles_exposes_only_live_helpers():
    from tradingagents.agents.utils import debate_roles

    assert callable(debate_roles.resolve_role_llm)
    assert callable(debate_roles.role_model_spec)
    for dead in ("role_tools", "BULL_TOOLS", "BEAR_TOOLS", "NEUTRAL_EVIDENCE_TOOLS"):
        assert not hasattr(debate_roles, dead), dead


# ---------------------------------------------------------------------------
# value_dip_tools now reuses analysis_tools._ohlcv / _scale_note
# ---------------------------------------------------------------------------


def test_value_dip_tools_share_the_analysis_tools_ohlcv_fetch(monkeypatch):
    """Stubbing the shared ``_load_ohlcv_df`` seam must feed value_dip_tools —
    proof it no longer carries a private fetch without the run cache or the
    ascending-date normalization."""
    closes = [100.0 + 0.5 * i for i in range(260)]
    T._clear_ohlcv_cache()
    monkeypatch.setattr(T, "_load_ohlcv_df", lambda ticker: _ohlcv_df(closes))
    try:
        out = V._ohlcv("DCODEX")
    finally:
        T._clear_ohlcv_cache()
    assert len(out["closes"]) == len(closes)
    assert out["closes"][-1] == pytest.approx(closes[-1])


def test_value_dip_tool_renders_against_the_shared_seam(monkeypatch):
    """get_bollinger_pct_b (which used the deleted private _ohlcv) still
    renders its computed block when only the shared fetch seam is stubbed."""
    closes = _dip_closes()
    T._clear_ohlcv_cache()
    monkeypatch.setattr(T, "_load_ohlcv_df", lambda ticker: _ohlcv_df(closes))
    try:
        out = V.get_bollinger_pct_b.invoke({"ticker": "DCODEX"})
    finally:
        T._clear_ohlcv_cache()
    assert "bollinger %b DCODEX:" in out
    assert "unavailable" not in out


# ---------------------------------------------------------------------------
# debate_structured: no wasted prime parse; repair loop still repairs
# ---------------------------------------------------------------------------


def test_repair_and_validate_repairs_from_the_model_response():
    """repair_and_validate consults only the LLM's corrected block — the
    deleted 'prime' parse of the prompt had no observable effect."""
    from tradingagents.agents.schemas import DebaterTurnPayload
    from tradingagents.agents.utils.debate_structured import repair_and_validate

    class _Resp:
        content = (
            '```json\n{"round_index": 1, "stance": "BULL", "core_thesis": "t", '
            '"quantitative_claims": [], "recommended_allocation_pct": 5.0}\n```'
        )

    class _LLM:
        def invoke(self, prompt):
            return _Resp()

    model, err = repair_and_validate(_LLM(), "prose, not JSON", DebaterTurnPayload)
    assert model is not None, err
    assert model.round_index == 1


# ---------------------------------------------------------------------------
# eodhd: the exhausted-retry path raises, never returns None
# ---------------------------------------------------------------------------


def test_eodhd_get_raises_when_retries_are_exhausted(monkeypatch):
    from tradingagents.dataflows import eodhd
    from tradingagents.dataflows.errors import VendorRateLimitError

    resp = mock.Mock()
    resp.status_code = 503
    monkeypatch.setattr(eodhd, "eodhd_api_key", lambda: "test-key")
    with mock.patch("requests.get", return_value=resp), pytest.raises(
        VendorRateLimitError
    ):
        eodhd._eodhd_get("eod/AAPL", {})
