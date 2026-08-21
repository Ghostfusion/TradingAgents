# Plan: Give the virtual agent better decision tools

**Status: implemented (P0-P2 all six tools landed + hermetic-tested, plus a follow-up batch of five sector/quality/safety/composite/tail tools).**
The six decision tools below are now exposed as @tools and bound to the
analyst tool nodes (and, for consensus, computed-injected into the PM
prompt). Each wraps an existing deterministic strategies function, so the
LLM agents cite computed stops, allocation, regime components, consensus,
momentum detail, and event multipliers instead of guessing them.

Auditing the current fork, the analyst LLMs already reason over many computed
numbers, but **several decision-critical deterministic functions exist and are
not exposed as tools** (so the agents either re-derive them from raw data, guess,
or never see them). This plan lists those gaps and proposes the least-invasive
way to close them: **expose each as a LangChain `@tool` bound to the right
analyst node** (market, fundamentals, news) — the "compute-as-tools" convention.

Every candidate below is **pure/offline**, deterministic, already implemented,
and has an existing wrapped cousin — so the integration is mechanical, not a new
algorithm.

---

## 0. The audit in one line

There are **~26 decision-relevant strategy functions** with **0 agent
references** today. They fall into four themes: **exit/cadence** (exits.py),
**portfolio/allocation** (portfolio.py), **regime structure** (regime.py),
**momentum microstructure** (momentum.py), plus a handful in
**reflection/consensus/price-action**. This plan surfaces the highest-value ones
to the right analyst tool loop.

Gap = a strategy function that produces a decision number an agent would want,
but no `@tool` in `analysis_tools.py` / `market_position_tools.py` / bound to an
analyst. Verified each candidate has zero references in
`agents/utils/*/` / `agents/analysts/*/`.

---

## 2. Candidate tools (highest value first)

### 2.1 Exits — `strategies/exits.py` → **market + trader decision**
Functions: `exit_check`, `stop_to_breakeven`, `target_level`, `net_of_cost`,
`rebalance_due`.

Why it helps: the trader decides Buy/Hold/Sell with an entry + stop. Today there
is **no** tool that produces a deterministic *ATR stop-to-breakeven / target /
exit-action* for a held position. `exit_check(entry, close, atr)` returns
`breakeven_stop`, `target`, `stop_hit`, `target_hit`, and a `holding_action`
(`target`/`stop`/`hold`) — exactly the number a trader should cite, not guess.

Proposed:
- `@tool get_exit_check(entry, close, atr, target_mult?, breakeven_cushion?)`
  → wraps `exits.exit_check`; bind to **market analyst** (it is the agent that
  argues price anchors) and make it available to the Trader prompt by listing it
  in the market node's tools.

### 2.2 Portfolio allocation — `strategies/portfolio.py`
Functions: `value_ratio_weights`, `capped_weights`, `sector_cap`,
`allocation_block`, `min_names_ok`, `adjust_for_caps`, `summary`.

Why: `get_portfolio_weights` already exposes `value_ratio_weights` to the
fundamentals analyst. But the **cap-respecting, allocation-block, min-names**
final alloc logic is NOT exposed — so the PM (which holds the final
`position_size`) cannot ask for a **cap-respected, diversified alloc** across a
book. This is a decision the PM would like, not the fundamentals.

Proposed: `@tool get_allocation(scores, sector_map, cap_pct?, max_name?)` →
wraps `adjust_for_caps` + `sector_cap`; bind to **portfolio_manager** (PM has
no tools today; add a computed-allocation input). This lets the PM ground its
size/look-link instead of guessing a % split.

### 2.3 Regime structure — `strategies/regime.py` → market analyst
Functions: `vol_percentile`, `realized_vol`, `trend_strength`, `choppiness`,
`regime_label`, `hmm_regime`.

Why: `get_regime_read` already calls `build_strategy_overlays` and returns a
one-line regime label + vol-target scale. But the **underlying vol/choppiness /
trend-strength components** are not exposed individually, so the market analyst
cannot drill into *why* the regime says what it does. That is a grounding gap.

Proposed: `@tool get_regime_components(ticker)` → runs `regime.vol_percentile` +
`trend_strength` + `choppiness` + `regime_label`; add to **market analyst**
tool list (or fold into `get_regime_read` output — cheaper).

### 2.4 Momentum microstructure — `strategies/momentum.py`
Functions already tooled via `get_momentum_scan`, but **deeper intraday
primitives** (`ema9`, `rvol`, `vwap`, `session_flags`, `psych_level`,
`first_pullback`) are not individually exposed to the market analyst for a
day-trade pre-filter. Consider a single `get_momentum_detail(ticker)` that
returns the pillar sub-scores + first-pullback + intraday flags, so the market
analyst cites exact momentum pillars (not a black-box).

### 2.5 Consensus / agreement — `strategies/consensus.py`
`consensus_from_score`, `agreement_score`. `get_agreement` is not a tool; the
PM only gets a free-text rating. Expose `get_consensus(rating_list)` to the PM
so the rating scale source is the *number*, not a narrative.

### 2.6 Price-action / PEAD — `strategies/events.py`
`position_mult_by_side`, `expected_drift_after`, `gap_up_qualifies`,
`consolidation_and_break`. Some are folded into `get_earnings_event_read`, but
the **integer multipliers** (post-earnings drift, gap-up gate) for a "sell-the-
news" beat are not surfaced as an integral repeatedly to the news analyst.
Recommend `get_beat_miss_sizing(day0_ret, side)` to the news node.

---

## 3. Cross-cutting decision helpers (root-free)

A few pure functions anywhere that usefully *ground* a decision but that the
agents never see because they are generic (not per-ticker):

- `evaluate.py::sharpe / max_drawdown / deflated_sharpe` — strategy *quality*
  scores the PM could ask for when deciding Hold vs trim.
- `book_risk.cvar` — already in risk governor; confirm the PM can ask for
  `get_cvar(returns)` to judge a tail budget.
- `reflection.build_reflection_context` — already injected as a prompt string,
  not a tool; that's fine (context, not a call).

These are lower priority; the four above are the highest signal.

---

## 4. How each was implemented

| Priority | Tool | Bound to | Why it improves the decision |
| --- | --- | --- | --- |
| P0 | `get_exit_check` | market analyst tool node | deterministic stop/target instead of LLM-picked stop_loss |
| P0 | `get_allocation` | fundamentals analyst tool node | cap/diversified book sizing from a scores dict |
| P1 | `get_regime_components` | market analyst | grounded vol/choppiness/trend for the regime read |
| P1 | `get_consensus` | tool + computed-injected PM prompt | numeric rating agreement for the PM call |
| P2 | `get_momentum_detail` | market analyst | exact pillar/pullback microstructure for intraday |
| P2 | `get_beat_miss_sizing` | news analyst | compute the post-earnings drift / gap-up multiplier |

Each is a `@tool` wrapping an existing strategy function, re-exported
in `agent_utils`, bound in both the analyst `tools` list and
`graph/trading_graph.py::_create_tool_nodes`, with hermetic tests in
`tests/test_analysis_tools.py`. The PM has no tool loop (NO_EXTERNAL_TOOLS), so
`get_consensus` is exposed as a tool AND its value is pre-fetched/parsed from
the risk debate and injected straight into the PM prompt (compute-as-tools
without a topology change).

## Follow-up batch (sector / quality / safety / composite / tail)

A later pass surfaced five more deterministic functions that were implemented
but not exposed to the analysts. Each is a `@tool` wrapping an existing
`strategies/*` pure function, bound in both the analyst tools list and
`_create_tool_nodes`, hermetic-tested in `tests/test_analysis_tools.py`:

| Tool | Wraps | Bound to | Why it improves the decision |
| --- | --- | --- | --- |
| `get_sector_rank(ticker)` | `sector_rank.rank_sectors` + `sector_standing` | market | grounds any sector-rotation / sector-leadership claim in the 11-SPDR 1m/3m momentum ranking + the ticker's standing |
| `get_strategy_quality(ticker, returns?)` | `evaluate` (cagr/sharp/vol/max_dd) | market | a deterministic risk-adjusted quality read (net CAGR, Sharpe, max drawdown) instead of a guessed quality narrative |
| `get_margin_of_safety(ticker, intrinsic)` | `normalized.margin_of_safety` | fundamentals | (intrinsic - price)/intrinsic band cited before any undervaluation claim |
| `get_composite_rank(ticker, factors?)` | `factors.composite_score` | fundamentals | cross-sectional value+momentum percentile vs industry peers (leader/laggard in the group) |
| `get_tail_risk(ticker, alpha?)` | `book_risk.cvar`/`simple_var`/`stress_loss` | market | explicit VaR/CVaR tail budget + -10% stress loss before a sizing/tail-risk claim |

---

## 5. What I did NOT propose (and why)

- **No new data sources** — this is about exposing what's already computed.
- **No new algorithms** — all candidates already exist as deterministic
  `strategies/*`.
- **No graph-topology change** — each is bound to an existing analyst node.
- **No LLM regression** — same provider, just more computed inputs before the
  decision.
- The rich layers (fundamentals `get_analyst_verdict`, catalyst,
  orderflow, swing, relative strength) are **already** tooled and left alone.

---

## 6. Impact summary

A run would produce a decision where the **stop, target, book allocation, regime
decomposition, rating consensus, momentum detail, and event multiplier** are all
**computed numbers the agents cite** instead of re-derived or guessed — exactly
the "compute, don't narrate" contract, extended to the exit/allocation/momentum/
regime micro-signals the current tool set doesn't surface.

When you're ready, the first cut is the two P0 tools (`get_exit_check`,
`get_allocation`), which directly upgrade the trader's stop/exit and the PM's
book-size — the two least-computed parts of the current decision output.