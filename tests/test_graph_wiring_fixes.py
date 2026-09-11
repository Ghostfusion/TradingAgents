"""Phase-D wiring fixes: registry credentials, checkpoint run scoping, parallel merge.

- ``registry._PROVIDER_CREDENTIAL_KEYS`` marks the five key-gated vendors
  (tiingo / twelve_data / stockdata / newsapi / benzinga) and
  ``method_requires_credentials`` reads a config instead of pretending every
  keyed vendor is unconfigured.
- ``_run_signature`` folds in ``enable_debate`` (the structured-debate node set
  is a different graph).
- checkpoint thread ids are scoped per run so concurrent runs of the same
  ticker+date can't clear each other's rows, while a crashed run still resumes
  under its own id.
- the parallel analyst node merges the non-report channels its subgraphs write
  (``tool_evidence`` per analyst key, plus any other channel).
"""

from __future__ import annotations

import contextlib
import tempfile
from types import SimpleNamespace
from typing import TypedDict

from langgraph.graph import END, StateGraph

from tradingagents.dataflows import registry as R
from tradingagents.graph import checkpointer, setup as graph_setup
from tradingagents.graph.propagation import Propagator
from tradingagents.graph.trading_graph import TradingAgentsGraph

KEY_GATED = {
    "tiingo": "tiingo_api_key",
    "twelve_data": "twelve_data_api_key",
    "stockdata": "stockdata_api_key",
    "newsapi": "newsapi_api_key",
    "benzinga": "benzinga_api_key",
}


# --------------------------------------------------------------------------- #
# (a) registry credentials
# --------------------------------------------------------------------------- #
def test_key_gated_vendors_are_credential_gated():
    for vendor, key in KEY_GATED.items():
        assert R.required_credentials(vendor) == (key,), vendor
        assert R.missing_credentials(vendor, {}) == [key], vendor
        assert R.missing_credentials(vendor, {key: "set"}) == [], vendor


def test_keyless_vendors_stay_keyless():
    assert R.required_credentials("yfinance") == ()
    assert R.missing_credentials("yfinance", {}) == []


def test_method_requires_credentials_respects_passed_cfg():
    # get_stock_data lists tiingo/twelve_data/stockdata; get_news lists
    # stockdata/newsapi/benzinga.
    unset = R.method_requires_credentials("get_stock_data", {})
    assert unset["tiingo"] == ["tiingo_api_key"]
    assert unset["twelve_data"] == ["twelve_data_api_key"]
    assert unset["stockdata"] == ["stockdata_api_key"]

    configured = dict.fromkeys(KEY_GATED.values(), "set")
    assert "tiingo" not in R.method_requires_credentials("get_stock_data", configured)
    news_missing = R.method_requires_credentials("get_news", configured)
    for vendor in ("stockdata", "newsapi", "benzinga"):
        assert vendor not in news_missing, vendor
    # keyless vendors are never reported as missing credentials
    assert "yfinance" not in unset


def test_method_requires_credentials_defaults_to_live_config(monkeypatch):
    import tradingagents.dataflows.config as dcfg

    monkeypatch.setattr(dcfg, "get_config", lambda: dict.fromkeys(KEY_GATED.values(), "set"))
    missing = R.method_requires_credentials("get_news")
    assert not (set(missing) & set(KEY_GATED)), missing

    monkeypatch.setattr(dcfg, "get_config", lambda: {})
    missing = R.method_requires_credentials("get_news")
    assert set(KEY_GATED) & set(missing) == {"stockdata", "newsapi", "benzinga"}


def test_command_map_keeps_shape():
    entry = R.command_map()["get_stock_data"]
    assert isinstance(entry["vendors"], list)
    assert "category" in entry
    assert entry["requires_credentials"]["tiingo"] == ["tiingo_api_key"]
    assert entry["keyless"] is True  # yfinance/moomoo serve it too


# --------------------------------------------------------------------------- #
# (b) _run_signature covers the debate mode
# --------------------------------------------------------------------------- #
def _bare_graph(config: dict) -> TradingAgentsGraph:
    g = object.__new__(TradingAgentsGraph)
    g.selected_analysts = ("market", "news")
    g.config = config
    return g


def test_run_signature_captures_debate_mode():
    base_config = {
        "max_debate_rounds": 1,
        "max_risk_discuss_rounds": 1,
        "analyst_concurrency": 1,
        "enable_debate": False,
    }
    off = _bare_graph(dict(base_config))._run_signature("stock")
    on = _bare_graph({**base_config, "enable_debate": True})._run_signature("stock")
    assert off != on
    assert checkpointer.thread_id("TEST", "2026-04-20", off) != checkpointer.thread_id("TEST", "2026-04-20", on)
    # stable for identical inputs
    assert off == _bare_graph(dict(base_config))._run_signature("stock")


# --------------------------------------------------------------------------- #
# (c) parallel merge carries tool_evidence
# --------------------------------------------------------------------------- #
class _StubSubgraph:
    def __init__(self, payload):
        self._payload = payload

    def invoke(self, state, config=None):  # noqa: ARG002 - mirrors CompiledGraph
        return {**state, **self._payload}


def _stub_plan():
    return SimpleNamespace(
        specs=[
            SimpleNamespace(key="market", report_key="market_report"),
            SimpleNamespace(key="news", report_key="news_report"),
        ]
    )


def test_parallel_merge_carries_tool_evidence():
    plan = _stub_plan()
    subgraphs = {
        "market": _StubSubgraph(
            {
                "messages": [],
                "market_report": "m",
                "tool_evidence": {"market": [{"tool": "get_stock_data", "status": "ok"}]},
            }
        ),
        "news": _StubSubgraph(
            {
                "messages": [],
                "news_report": "n",
                "tool_evidence": {"news": [{"tool": "get_news", "status": "ok"}]},
                # a channel the merge must carry even though it is not a report key
                "security_type": "ETF",
            }
        ),
    }
    state = {"messages": [], "past_context": "ctx"}
    out = graph_setup.make_parallel_analyst_node(plan, subgraphs, 2)(state)

    assert out["market_report"] == "m"
    assert out["news_report"] == "n"
    assert set(out["tool_evidence"]) == {"market", "news"}
    assert out["tool_evidence"]["news"] == [{"tool": "get_news", "status": "ok"}]
    assert out["security_type"] == "ETF"
    assert out["past_context"] == "ctx"
    # the caller's state dict is not mutated
    assert "tool_evidence" not in state


def test_parallel_merge_carries_evidence_from_real_subgraphs():
    """The merged channel must survive a real compiled AgentState subgraph."""
    from langchain_core.messages import AIMessage
    from langgraph.prebuilt import ToolNode

    from tradingagents.graph.analyst_execution import build_analyst_execution_plan
    from tradingagents.graph.conditional_logic import ConditionalLogic

    plan = build_analyst_execution_plan(("market",))

    def analyst_node(state):
        return {
            "messages": [AIMessage(content="market report")],
            "market_report": "market report",
            "tool_evidence": {"market": [{"tool": "get_stock_data", "status": "ok"}]},
        }

    subgraphs = {
        spec.key: graph_setup._build_analyst_subgraph(
            spec,
            lambda: analyst_node,
            ToolNode([]),
            ConditionalLogic(max_debate_rounds=1, max_risk_discuss_rounds=1),
        )
        for spec in plan.specs
    }
    out = graph_setup.make_parallel_analyst_node(plan, subgraphs, 1)({"messages": []})
    assert out["tool_evidence"] == {"market": [{"tool": "get_stock_data", "status": "ok"}]}


# --------------------------------------------------------------------------- #
# (d) run-scoped checkpoint threads
# --------------------------------------------------------------------------- #
class _CrashState(TypedDict):
    count: int


_CRASH = {"on": False}


def _node_a(state: _CrashState) -> dict:
    return {"count": state["count"] + 1}


def _node_b(state: _CrashState) -> dict:
    if _CRASH["on"]:
        raise RuntimeError("simulated mid-analysis crash")
    return {"count": state["count"] + 10}


def _crash_graph():
    builder = StateGraph(_CrashState)
    builder.add_node("analyst", _node_a)
    builder.add_node("trader", _node_b)
    builder.set_entry_point("analyst")
    builder.add_edge("analyst", "trader")
    builder.add_edge("trader", END)
    return builder


def test_run_id_namespaces_thread_id():
    args = ("TEST", "2026-04-20", "analysts=market|asset=stock")
    run_a = checkpointer.thread_id(*args, "run-a")
    run_b = checkpointer.thread_id(*args, "run-b")
    assert run_a != run_b
    assert run_a == checkpointer.thread_id(*args, "run-a")  # deterministic per run
    assert run_a != checkpointer.thread_id(*args)  # run-scoped differs from the shared thread
    # explicit-resume contract: no run id keeps the pre-run-scoped id
    assert checkpointer.thread_id(*args) == checkpointer.thread_id(*args, "")


def test_run_scoped_checkpoints_do_not_clobber_each_other():
    with tempfile.TemporaryDirectory() as tmp:
        ticker, date, sig = "TEST", "2026-04-20", "analysts=market|asset=stock"
        _CRASH["on"] = True
        for run_id in ("run-a", "run-b"):
            tid = checkpointer.thread_id(ticker, date, sig, run_id)
            with checkpointer.get_checkpointer(tmp, ticker) as saver:
                graph = _crash_graph().compile(checkpointer=saver)
                with contextlib.suppress(RuntimeError):
                    graph.invoke({"count": 0}, config={"configurable": {"thread_id": tid}})

        assert checkpointer.checkpoint_step(tmp, ticker, date, sig, "run-a") == 1
        assert checkpointer.checkpoint_step(tmp, ticker, date, sig, "run-b") == 1

        # Clearing run-a's thread leaves run-b's rows alone.
        checkpointer.clear_checkpoint(tmp, ticker, date, sig, "run-a")
        assert not checkpointer.has_checkpoint(tmp, ticker, date, sig, "run-a")
        assert checkpointer.has_checkpoint(tmp, ticker, date, sig, "run-b")

        # The same run still resumes from its own checkpoint.
        _CRASH["on"] = False
        with checkpointer.get_checkpointer(tmp, ticker) as saver:
            graph = _crash_graph().compile(checkpointer=saver)
            result = graph.invoke(
                None,
                config={"configurable": {"thread_id": checkpointer.thread_id(ticker, date, sig, "run-b")}},
            )
        assert result["count"] == 11


def test_resolve_run_id_resumes_unfinished_run_then_restarts():
    with tempfile.TemporaryDirectory() as tmp:
        ticker, date, sig = "TEST", "2026-04-20", "analysts=market|asset=stock"

        explicit = checkpointer.resolve_run_id(tmp, ticker, date, sig, "pinned")
        assert explicit == "pinned"

        run_id = checkpointer.resolve_run_id(tmp, ticker, date, sig)
        assert run_id

        # Nothing checkpointed yet -> a fresh id, not a stale reuse.
        resumed_from_nothing = checkpointer.resolve_run_id(tmp, ticker, date, sig)
        assert resumed_from_nothing != run_id

        # Crash the run the marker currently points at -> its id is reused
        # (resume path).
        _CRASH["on"] = True
        with checkpointer.get_checkpointer(tmp, ticker) as saver:
            graph = _crash_graph().compile(checkpointer=saver)
            with contextlib.suppress(RuntimeError):
                graph.invoke(
                    {"count": 0},
                    config={
                        "configurable": {
                            "thread_id": checkpointer.thread_id(
                                ticker, date, sig, resumed_from_nothing
                            )
                        }
                    },
                )
        _CRASH["on"] = False
        assert checkpointer.resolve_run_id(tmp, ticker, date, sig) == resumed_from_nothing

        # A completed run forgets its marker -> the next run gets a new id.
        checkpointer.forget_run(tmp, ticker, date, sig, resumed_from_nothing)
        assert checkpointer.resolve_run_id(tmp, ticker, date, sig) != resumed_from_nothing


def test_resolve_run_id_is_graph_shape_scoped():
    with tempfile.TemporaryDirectory() as tmp:
        ticker, date = "TEST", "2026-04-20"
        sig_a = "analysts=market|asset=stock"
        sig_b = "analysts=market,news|asset=stock"
        run_a = checkpointer.resolve_run_id(tmp, ticker, date, sig_a)

        _CRASH["on"] = True
        with checkpointer.get_checkpointer(tmp, ticker) as saver:
            graph = _crash_graph().compile(checkpointer=saver)
            with contextlib.suppress(RuntimeError):
                graph.invoke(
                    {"count": 0},
                    config={
                        "configurable": {
                            "thread_id": checkpointer.thread_id(ticker, date, sig_a, run_a)
                        }
                    },
                )
        _CRASH["on"] = False

        assert checkpointer.resolve_run_id(tmp, ticker, date, sig_a) == run_a  # resumable
        assert checkpointer.resolve_run_id(tmp, ticker, date, sig_b) != run_a  # other graph shape


def test_run_graph_threads_and_clears_only_its_own_run():
    """_run_graph resumes/clears the run it was scoped to, not a stranger's."""
    ticker, date, sig = "TEST", "2026-04-20", "analysts=market|asset=stock"
    with tempfile.TemporaryDirectory() as tmp:
        _CRASH["on"] = True
        for run_id in ("run-a", "run-b"):
            with checkpointer.get_checkpointer(tmp, ticker) as saver:
                graph = _crash_graph().compile(checkpointer=saver)
                with contextlib.suppress(RuntimeError):
                    graph.invoke(
                        {"count": 0},
                        config={
                            "configurable": {
                                "thread_id": checkpointer.thread_id(ticker, date, sig, run_id)
                            }
                        },
                    )
        _CRASH["on"] = False

        captured: dict = {}

        class _RecordingGraph:
            def invoke(self, state, **kwargs):  # noqa: ARG002 - mirrors CompiledGraph
                captured.update(kwargs["config"]["configurable"])
                return {"final_trade_decision": "decision"}

        g = object.__new__(TradingAgentsGraph)
        g.debug = False
        g.graph = _RecordingGraph()
        g.curr_state = None
        g.config = {"checkpoint_enabled": True, "data_cache_dir": tmp}
        g.propagator = Propagator()
        g.memory_log = SimpleNamespace(
            get_past_context=lambda _ticker: "",
            get_track_record_stats=lambda _ticker: "",
            store_decision=lambda **_kwargs: None,
        )
        g.resolve_instrument_context = lambda *a, **k: ""
        g._compiled_decision_context = lambda *a, **k: ""
        g._apply_strategy_overlays = lambda state, _ticker: state
        g._log_state = lambda *a, **k: None
        g.process_signal = lambda _decision: None
        g._checkpoint_scope = (sig, "run-a")

        g._run_graph(ticker, date)

        assert captured["thread_id"] == checkpointer.thread_id(ticker, date, sig, "run-a")
        assert not checkpointer.has_checkpoint(tmp, ticker, date, sig, "run-a")
        assert checkpointer.has_checkpoint(tmp, ticker, date, sig, "run-b")
