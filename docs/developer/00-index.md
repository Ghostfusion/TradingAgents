# TradingAgents Developer Docs — Index

This folder is the **map** for a human developer joining this fork. It covers
the **entire project** — topology, graph, workflow, data layer, strategies,
agents, entry points, persistence, and the Massive.com integration — not just
recent changes. Read [`Machine Workflow`](02-01-graph-workflow.md) first, then
drill into whatever area you are touching.

## Document set

| # | File | What it tells you |
| --- | --- | --- |
| 0 | `00-index.md` (this) | orientation + how docs relate |
| 1 | `01-topology.md` | package/layer topology, where every module lives |
| 2 | `02-graph-workflow.md` | **LangGraph node topology + the propagate() run** |
| 2.1 | `02-01-graph-workflow.md` | the end-to-end run from entry to decision |
| 3 | `03-dataflow-vendors.md` | vendor layer, routing, config, cache, errors |
| 4 | `04-strategies.md` | deterministic strategy overlays & calculators |
| 5 | `05-agents-tools.md` | agent prompts, structured output, @tool binding |
| 6 | `06-entrypoints.md` | CLI, batch, pipeline, screener, python API |
| 7 | `07-persistence.md` | memory log, checkpoints, reports, caches |
| 8 | `08-development.md` | how to add a feature, test, keep docs true |
| 9 | `09-massive-integration.md` | the Massive.com add-on and its seams |
| 10 | `10-tests-layout.md` | the `tests/` directory map, fixtures, conventions |
| 11 | `11-agent-decision-tools.md` | audit + plan: deterministic functions to expose as agent tools |
| 12 | `12-data-providers.md` | the 13 data providers/sources and how each is wired |

Companion docs (repo root `docs/`):
- [`docs/AGENT_ONBOARDING.md`](../AGENT_ONBOARDING.md) — environment runbook / gotchas (read first).
- [`docs/api_reference.md`](../api_reference.md) — canonical config-key, tool, vendor tables.
- [`docs/howto_end_to_end.md`](../howto_end_to_end.md) — daily workflow (screener → pipeline → reports).

## A one-paragraph mental model

TradingAgents is a **LangGraph state machine over LLM agents**. A run starts
with an instrument identity, fans out to 4 analyst teams (market, sentiment,
news, fundamentals) that each run a **tool-calling LLM loop** against a
configurable vendor layer, then feeds a **Bull/Bear debate**, a **Research
Manager**, a **Trader**, a **3-way risk debate**, and a **Portfolio Manager**
that emits a structured decision. After the graph finishes, a **deterministic
strategy-overlay pipeline** (regime → orderflow → catalyst → position contract
→ risk governor → computed context; opt-in tranche-scaling risk fold) adjusts
the size / vetoes risk. The
decision is logged to memory; the next same-ticker run resolves the realized
return.

```
vendor layer (data) → analyst tool loops → bull/bear → research mgr
  → trader → risk debate → portfolio mgr → structured decision
  → deterministic overlays (size/veto) → memory log → reports
```

## Topology at a glance

```
tradingagents/
├─ agents/        # prompts + LangChain tool binding per agent
├─ dataflows/     # vendor layer: interface.py, config.py, errors.py, vendors
├─ graph/         # LangGraph state machine + overlays + propagation
├─ strategies/    # deterministic calculators (no LLM)
├─ llm_clients/   # provider registry / factories
├─ default_config.py  # DEFAULT_CONFIG + TRADINGAGENTS_* env overrides
└─ reporting.py   # report tree writer + TOC
scripts/          # value_screener, action_report, rebuild_complete_report, eval, cli helpers
batch.py          # headless concurrent runner
pipeline.py       # screen→composite-rank→top-N→batch (B2)
main.py           # minimal python API demo
```

See [`01-topology.md`](01-topology.md) for the full file map and responsibilities.
See [`02-graph-workflow.md`](02-graph-workflow.md) for the run and node edges.

## Conventions that apply everywhere

1. **`py -3.12` everywhere** — never bare `python` (agent venv, no pytest).
2. **Compute-as-tools** — expose deterministic calculations as `@tool`s so the
   LLM agents reason over computed numbers, never invented ones.
3. **Docs stay true** — update README + docs + CHANGELOG on any behavior change.
4. **Commit + push** when done (Conventional Commits).
5. **No secrets in commits** — keys live in `.env` (gitignored).

Read each referenced doc fully before relying on any module.