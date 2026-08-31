"""Risk-calc -> agent wiring guards (audit implementation, 2026-08-31).

Covers the 7-phase plan's wiring contract:
- P1: every tool bound to an analyst LLM is executable in that analyst's
  ToolNode (bound ⊆ node); the market analyst reaches the previously orphaned
  quant-risk tools.
- P2: get_risk_gate exposes the FULL governor surface (daily-loss / HWM /
  liquidity / capital-at-risk all reach `govern`), plus the new risk tools.
- P3: the computed decision context carries the risk factsheet (limits
  registry, vol estimates, tranche capital-at-risk, fixed-risk size).
- P4/P5: the in-node risk/trader tool loop terminates, executes real tools,
  and degrades to plain invocation when a provider cannot bind tools.

Hermetic: no network, no real LLM. Mocked vendor/config/LLM only.
"""

import pytest

from tradingagents.agents.utils.analysis_tools import (
    get_alpha_scoring,
    get_exit_overrides,
    get_fixed_risk_size,
    get_pair_risk,
    get_pre_trade_read,
    get_regime_gate_read,
    get_risk_gate,
    get_trade_excursions,
    get_vif_read,
    get_vol_cones,
)

pytestmark = pytest.mark.timeout(120)

# ---------------------------------------------------------------------------
# P1 — binding parity: every analyst-bound tool is executable in its ToolNode
# ---------------------------------------------------------------------------

TOOLNODE_KEYS = ("market", "news", "fundamentals")
ANALYST_FILES = {
    "market": "tradingagents/agents/analysts/market_analyst.py",
    "news": "tradingagents/agents/analysts/news_analyst.py",
    "fundamentals": "tradingagents/agents/analysts/fundamentals_analyst.py",
}


@pytest.mark.unit
def test_analyst_bound_tools_all_executable_in_toolnode():
    """Regression guard for the Phase-1 18-tool gap: no analyst may bind a
    tool the ToolNode cannot execute (the LLM would error 'not a valid tool')."""
    import re

    from tradingagents.graph.trading_graph import TradingAgentsGraph

    nodes = TradingAgentsGraph._create_tool_nodes(None)
    for key, path in ANALYST_FILES.items():
        with open(path, encoding="utf-8") as fh:
            src = fh.read()
        m = re.search(r"tools = \[(.*?)\]\n", src, re.S)
        assert m, f"no tools list in {path}"
        bound = set(re.findall(r"get_[a-z_0-9]+", m.group(1)))
        node = set(nodes[key].tools_by_name)
        missing = sorted(bound - node)
        assert not missing, f"{key} analyst binds tools missing from its ToolNode: {missing}"


@pytest.mark.unit
def test_market_analyst_reaches_quant_risk_tools():
    """The previously-unreachable quant-risk tools are bound to the market
    LLM (Phase-1 audit fix)."""
    import re

    with open("tradingagents/agents/analysts/market_analyst.py", encoding="utf-8") as fh:
        src = fh.read()
    m = re.search(r"tools = \[(.*?)\]\n", src, re.S)
    bound = set(re.findall(r"get_[a-z_0-9]+", m.group(1)))
    expected = {
        "get_horizon_var",
        "get_downside_read",
        "get_trailing_exit",
        "get_exit_plan",
        "get_scaleout_plan",
        "get_risk_parity_alloc",
        "get_payoff_asymmetry",
        "get_book_correlation",
        "get_capm_risk",
        "get_normality",
        "get_unit_root",
        "get_relative_rotation",
        "get_clenow_momentum",
        "get_sentiment_computed",
        "get_market_movers",
        "get_variance_premium",
    }
    missing = expected - bound
    assert not missing, f"market analyst still cannot reach: {sorted(missing)}"


@pytest.mark.unit
def test_orphan_tools_bound_to_a_node():
    from tradingagents.graph.trading_graph import TradingAgentsGraph

    nodes = TradingAgentsGraph._create_tool_nodes(None)
    all_tools = set()
    for key in TOOLNODE_KEYS:
        all_tools |= set(nodes[key].tools_by_name)
    for orphan in ("get_variance_premium", "get_credit_spread_read"):
        assert orphan in all_tools, f"{orphan} is bound to no ToolNode"


# ---------------------------------------------------------------------------
# P2 — get_risk_gate full governor surface
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_risk_gate_daily_loss_rejects():
    out = get_risk_gate.invoke({"size_pct": 0.10, "daily_loss_pct": 0.05})
    assert "REJECT" in out
    assert "daily_loss" in out


@pytest.mark.unit
def test_risk_gate_hwm_hard_tier_rejects():
    out = get_risk_gate.invoke({"size_pct": 0.10, "hwm_drawdown_pct": 0.25})
    assert "REJECT" in out
    assert "hwm_drawdown" in out


@pytest.mark.unit
def test_risk_gate_liquidity_illiquid_rejects():
    out = get_risk_gate.invoke({"size_pct": 0.10, "liquidity_verdict": "ILLIQUID"})
    assert "REJECT" in out
    assert "ILLIQUID" in out.upper()


@pytest.mark.unit
def test_risk_gate_capital_at_risk_rejects():
    out = get_risk_gate.invoke(
        {"size_pct": 0.10, "capital_at_risk_pct": 0.05, "risk_cap_pct": 0.015}
    )
    assert "REJECT" in out
    assert "capital-at-risk" in out


@pytest.mark.unit
def test_risk_gate_pass_shows_inputs():
    out = get_risk_gate.invoke({"size_pct": 0.05})
    assert "PASS" in out


# ---------------------------------------------------------------------------
# P2 — new risk tools (pure math on synthetic inputs)
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_fixed_risk_size_math():
    out = get_fixed_risk_size.invoke(
        {"equity": 100000.0, "risk_frac": 0.01, "entry": 100.0, "stop_loss": 95.0}
    )
    # riskable = 1000 / 5 = 200 units
    assert "total=200" in out
    out2 = get_fixed_risk_size.invoke(
        {"equity": 100000.0, "risk_frac": 0.01, "entry": 100.0, "stop_loss": 95.0, "units": 3}
    )
    assert "3 tranche(s)" in out2


@pytest.mark.unit
def test_exit_overrides_liquidates_breach():
    out = get_exit_overrides.invoke(
        {
            "targets": {"AAPL": 0.1, "MSFT": 0.1},
            "state_by_name": {
                "AAPL": {"entry": 100, "peak": 110, "current": 100},  # -9.1% vs peak
                "MSFT": {"entry": 100, "peak": 110, "current": 109},  # fine
            },
            "max_drawdown_pct": 0.05,
        }
    )
    assert "AAPL=0" in out
    assert "MSFT" not in out.split("trailing overrides:")[0].replace("AAPL", "")


@pytest.mark.unit
def test_pre_trade_read_cap_blocks():
    out = get_pre_trade_read.invoke(
        {"symbol": "AAPL", "notional": 50000.0, "max_notional": 10000.0}
    )
    assert "REJECT" in out
    assert "50,000" in out


@pytest.mark.unit
def test_alpha_scoring_magnitude_error():
    out = get_alpha_scoring.invoke(
        {
            "direction": "up",
            "predicted_magnitude": 0.12,
            "period_days": 30,
            "actual_return": 0.02,
        }
    )
    assert "hit=True" in out
    assert "magnitude_err=-0.1" in out


@pytest.mark.unit
def test_pair_risk_on_cointegrated_pair():
    import numpy as np

    rng = np.random.default_rng(7)
    x = list(np.cumsum(rng.normal(0, 1, 300)) + 100)
    # y = 2*x + stationary noise -> cointegrated
    noise = [n * 0.05 for n in rng.normal(0, 1, 300)]
    y = [2 * a + b for a, b in zip(x, noise, strict=True)]
    out = get_pair_risk.invoke({"x": x, "y": y, "maxlag": 1})
    assert "cointegrated=True" in out


@pytest.mark.unit
def test_vol_cones_requires_history_guards():
    # short series -> explicit unavailable, never fabricated
    out = get_vol_cones.invoke({"ticker": "AAPL"})
    assert isinstance(out, str)
    assert "unavailable" in out or "vol cones" in out


@pytest.mark.unit
def test_regime_gate_read_requires_history():
    # uses the run cache; offline it must degrade to unavailable, not raise
    out = get_regime_gate_read.invoke({"ticker": "AAPL"})
    assert isinstance(out, str)
    assert "unavailable" in out or "verdict=" in out


@pytest.mark.unit
def test_vif_and_excursions_degrade_cleanly():
    assert "unavailable" in get_vif_read.invoke({"columns": {"a": [1, 2]}}).lower()
    assert "unavailable" in get_trade_excursions.invoke({"trades": []}).lower()


# ---------------------------------------------------------------------------
# P4/P5 — in-node tool loop
# ---------------------------------------------------------------------------


class _FakeResp:
    def __init__(self, content="", tool_calls=None):
        self.content = content
        self.tool_calls = tool_calls or []


class _FakeLLM:
    """First call requests get_risk_gate, second returns prose."""

    def __init__(self):
        self.calls = 0

    def bind_tools(self, tools):
        return _FakeChain(self)

    def invoke(self, prompt):  # fallback path
        return _FakeResp(content="fallback prose")


class _FakeChain:
    def __init__(self, llm):
        self.llm = llm

    def invoke(self, messages):
        self.llm.calls += 1
        if self.llm.calls == 1:
            return _FakeResp(
                tool_calls=[{"name": "get_risk_gate", "args": {"size_pct": 0.25}, "id": "t1"}]
            )
        tool_msgs = [m for m in messages if getattr(m, "type", "") == "tool"]
        return _FakeResp(content="gate " + (tool_msgs[-1].content[:40] if tool_msgs else "none"))


@pytest.mark.unit
def test_run_tool_loop_executes_real_tool_and_terminates():
    from tradingagents.agents.utils.risk_tool_loop import (
        RISK_DEBATOR_TOOLS,
        run_tool_loop,
    )

    text, transcript = run_tool_loop(_FakeLLM(), "proposed 25%", RISK_DEBATOR_TOOLS)
    assert "gate" in text
    assert transcript and "get_risk_gate" in transcript[0]
    assert "PASS" in text or "REJECT" in text or "WARN" in text


@pytest.mark.unit
def test_run_tool_loop_cap_always_terminates():
    from tradingagents.agents.utils.risk_tool_loop import (
        RISK_DEBATOR_TOOLS,
        run_tool_loop,
    )

    class _EndlessLLM:
        def bind_tools(self, tools):
            return _EndlessChain()

    class _EndlessChain:
        def invoke(self, messages):
            return _FakeResp(tool_calls=[{"name": "get_risk_gate", "args": {"size_pct": 0.1}, "id": "x"}])

    # The cap turn strips dangling tool_calls and returns the terminal prose.
    text, transcript = run_tool_loop(_EndlessLLM(), "p", RISK_DEBATOR_TOOLS, max_rounds=1)
    assert isinstance(text, str)
    assert len(transcript) <= 1


@pytest.mark.unit
def test_run_tool_loop_falls_back_when_bind_fails():
    from tradingagents.agents.utils.risk_tool_loop import (
        RISK_DEBATOR_TOOLS,
        run_tool_loop,
    )

    class _NoBind:
        def bind_tools(self, tools):
            raise NotImplementedError("no tool binding")

        def invoke(self, prompt):
            return _FakeResp(content="fallback prose")

    text, transcript = run_tool_loop(_NoBind(), "p", RISK_DEBATOR_TOOLS)
    assert text == "fallback prose"
    assert transcript == []


@pytest.mark.unit
def test_debator_node_runs_with_plain_llm():
    """A debator whose provider cannot bind tools still produces an argument
    (degradation path never breaks the risk debate)."""
    from tradingagents.agents.risk_mgmt.aggressive_debator import create_aggressive_debator

    class _Plain:
        def bind_tools(self, tools):
            raise NotImplementedError

        def invoke(self, prompt):
            return _FakeResp(content="aggressive case: gate PASS per computed limits")

    node = create_aggressive_debator(_Plain())
    state = {
        "risk_debate_state": {
            "history": "",
            "aggressive_history": "",
            "conservative_history": "",
            "neutral_history": "",
            "latest_speaker": "",
            "current_aggressive_response": "",
            "current_conservative_response": "",
            "current_neutral_response": "",
            "count": 0,
        },
        "market_report": "m",
        "sentiment_report": "s",
        "news_report": "n",
        "fundamentals_report": "f",
        "instrument_context": "IC",
        "trader_investment_plan": "BUY",
        "computed_decision_context": "gate PASS",
        "company_of_interest": "AAPL",
    }
    out = node(state)
    arg = out["risk_debate_state"]["aggressive_history"]
    assert "Aggressive Analyst: aggressive case" in arg
    assert out["risk_debate_state"]["count"] == state["risk_debate_state"]["count"] + 1


# ---------------------------------------------------------------------------
# P3 — decision-context risk factsheet
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_compiled_decision_context_emits_risk_factsheet():
    """The limits registry / vol estimates / tranche / fixed-risk lines are
    present in the compiled decision context (monkeypatched closes + config)."""
    from tradingagents.graph.trading_graph import TradingAgentsGraph

    ta = TradingAgentsGraph.__new__(TradingAgentsGraph)
    ta.config = {
        "enable_risk_governor": True,
        "enable_tranche_risk": True,
        "tranche_weights": (0.3, 0.3, 0.4),
        "tranche_stop_mult": 1.5,
        "tranche_risk_pct": 0.015,
        "tranche_account": 100000.0,
        "max_position_pct": 0.30,
        "risk_max_position_pct": 0.45,
        "sector_cap_limit": 0.35,
        "risk_per_trade": 0.01,
        "enable_preopen_rvol": False,
        "enable_preopen_depth": False,
    }
    ta.memory_log = None
    closes = [100.0 + i * 0.1 for i in range(120)]
    ta._try_fetch_closes = lambda ticker, days=320: closes  # noqa: ARG005
    ctx = ta._compiled_decision_context("AAPL", {})
    assert "limits registry" in ctx
    assert "vol" in ctx
    assert "fixed-risk size" in ctx
    assert "tranche risk" in ctx or "tranche" in ctx


@pytest.mark.unit
def test_decision_context_factsheet_budget():
    from tradingagents.graph.trading_graph import TradingAgentsGraph

    ta = TradingAgentsGraph.__new__(TradingAgentsGraph)
    ta.config = {
        "enable_risk_governor": True,
        "enable_tranche_risk": True,
        "enable_preopen_rvol": False,
        "enable_preopen_depth": False,
        "tranche_weights": (0.3, 0.3, 0.4),
        "tranche_stop_mult": 1.5,
        "tranche_risk_pct": 0.015,
        "tranche_account": 100000.0,
        "max_position_pct": 0.30,
        "risk_max_position_pct": 0.45,
        "sector_cap_limit": 0.35,
        "risk_per_trade": 0.01,
    }
    ta.memory_log = None
    closes = [100.0 + i * 0.1 for i in range(120)]
    ta._try_fetch_closes = lambda ticker, days=320: closes  # noqa: ARG005
    ctx = ta._compiled_decision_context("AAPL", {})
    assert len(ctx) < 4000, f"factsheet exceeded budget: {len(ctx)} chars"
