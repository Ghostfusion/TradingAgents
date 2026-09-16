# OpenRouter large-prompt timeouts & prefix caching — implementation plan

Status: **implemented 2026-09-14** — W1 (streaming), W2 (provider routing), W3
(`session_id` sticky routing), W4 (the prefix-cache defect), W6-telemetry and W7 (cache
telemetry) are in the code; W5 (prompt size) and W6's provider rotation stay open (§9).
Scope: every LLM call this repo makes through `llm_provider=openrouter`. Evidence base:
this repo's failure journal, the OpenRouter docs (fetched live 2026-09-14), a code audit
of the prefix path, and one live two-turn probe (§9).

Related prior art in-repo: `TRADINGAGENTS_OPENROUTER_IGNORE_PROVIDERS` (provider.ignore,
2026-08-24), `TRADINGAGENTS_OPENROUTER_REASONING_EFFORT` (2026-09-07),
default `request_timeout=300` (`tests/test_llm_client_timeout.py`).

---

## 0. TL;DR — ranked workstreams

| # | Workstream | Cuts | Effort | Risk | Default |
|---|---|---|---|---|---|
| W1 | Stream the response (`streaming=True`) | 504 exposure on the client↔OpenRouter leg; partial-output recovery | S | M | opt-in flag, flip after A/B |
| W2 | Harden `extra_body.provider` routing (sort/latency floor + the existing ignore list) | TTFT variance, queueing on slow hosts | S | L | sort=throughput opt-in; ignore list is config |
| W3 | `session_id` sticky routing | cache-hit rate (DeepSeek read = **0.1×** input price) + near-zero re-prefill | S | L | opt-in flag |
| W4 | Prefix-cache **stability** — *audited: confirmed defect, cache is dead at token 0 every tool round* | prefill time **and** cost on every tool round of every analyst | M | M | no flag (invariant fix) |
| W5 | Shrink the prompt that actually 504s (Trader/RM/PM terminals, tool catalog, evidence blocks) | absolute prefill time | L | M | separate plan |
| W6 | Failure semantics: typed-504 detection + retry-amplification control | wasted re-prefills, time-to-fallback | S | L | no flag (telemetry) + flag for rotation |
| W7 | Cache telemetry (`cache_read` / `cache_creation` into footer + journal) | nothing directly — it is how W1–W5 are *proven* | S | L | always on |

**Landed (2026-09-14).** W4's fix first (it gates everything else: with the prefix moving
every round, a sticky session would pin a host to a cache that never hits), then the W7
telemetry that measures it, then W1/W2/W3 in one change to `openai_client.py` + the
config. W6's rotation half is deferred with a reason (§9). W5 is untouched — it needs its
own A/B and it is the only remaining lever on absolute prefill time.

**Result (measured live, same client, same 6,043-token prompt, `deepseek/deepseek-v4.1-flash`
through OpenRouter with `STREAMING=true` + `SESSION_ID=auto`):**

| turn | `input_tokens` | `input_token_details.cache_read` |
|---|---|---|
| 1 | 6,043 | 0 |
| 2 | 6,043 | **5,888** (~97%) |

So the cache now hits, the streamed `invoke()` still reports `usage_metadata` (the risk
noted in §W1 is refuted empirically), and the second turn's input is billed at DeepSeek's
0.1x cache-read rate instead of the full input rate.

---

## 1. Evidence in this repo

The premise (a large prompt ⇒ gateway idle-timeout ⇒ 504) is real but **rare here**.
Tally of the 443 entries in `FailureLog/` (journal dir = `data_cache_dir/llm_failures`,
written by `tradingagents/agents/utils/llm_failure_journal.py`):

| Class | Count |
|---|---|
| `structured output returned no parsed result` | 238 |
| `'_LLM' object has no attribute 'invoke'` (test-harness artifact) | 112 |
| length-limit truncation (`LengthFinishReasonError`, `completion_tokens=16000`) | 46 |
| `cap-forced terminal turn returned empty content` | 13 |
| `debate/structured_turn` parse failures | 16 |
| **provider timeout / 504** | **1** |

The single timeout record is the newest one and it is exactly the large-prompt case:

```json
// FailureLog/llm_failure_20260914_161016_16527.json
{"stage": "structured/Trader", "exception": "ValueError",
 "message": "{'message': 'The operation was aborted', 'code': 504,
              'metadata': {'error_type': 'timeout'}}"}
```

`error_type: "timeout"` is OpenRouter's typed code for **HTTP 504**, defined as
*"The provider did not respond within the allowed time"*
([Errors and Debugging](https://openrouter.ai/docs/api_reference/errors-and-debugging)).
So: the **provider/OpenRouter budget for time-to-first-response was exceeded during
prompt processing**, not our client budget (we allow `request_timeout=300`,
`openai_client.py:345`).

The two adjacent large-prompt symptoms, measured in the same journal, share the
mechanism (the biggest prompts in the stack are answered last and warm/without cache):

* `finalize_messages/Market Analyst` — `input_tokens: 33242`, cap-forced turn returned
  empty (reasoning burn; already mitigated by `TRADINGAGENTS_OPENROUTER_REASONING_EFFORT`,
  which is set to `high` in `.env:245`).
* `structured/Trader`, `structured/Research Manager`, `structured/Portfolio Manager` are
  the terminal stages that aggregate **all** analyst reports + evidence + debate + risk
  turns — the largest prompts in the graph, and the ones that fail.

Config as it stood before this change (`.env`, pre-2026-09-14 snapshot — the shipped
values are in §9): provider `openrouter`, both tiers
`deepseek/deepseek-v4.1-flash`, `TRADINGAGENTS_MAX_OUTPUT_TOKENS_QUICK=16000`,
`_DEEP=8000`, `TRADINGAGENTS_LLM_MAX_RETRIES=3`, `TRADINGAGENTS_OPENROUTER_IGNORE_PROVIDERS=`
(**empty**), reasoning effort `high`, **`TRADINGAGENTS_ANALYST_FORCED_TOOLS=ALL`**
(`.env:189` — every tool registered to each analyst is gathered deterministically and
rendered into its system prompt; see §W4/W5), `TRADINGAGENTS_ENABLE_EVIDENCE_SYMMETRY=true`
(`.env:279`).

Note the word *warm* above is aspirational: §W4 shows the analyst prefix is structurally
cold in the current code, so there is no warming to lose — that is a finding of this plan,
not an assumption of it.

---

## 2. Mechanism (what the docs actually say)

1. **Prefill vs decode.** A large prompt costs GPU prefill (KV-cache build) before any
   token is emitted. Nothing is written to the socket during prefill.
2. **Two different timers.** (a) our client timeout (`request_timeout=300`, applied to
   the SDK), (b) OpenRouter's per-provider response budget. The observed failure is (b),
   surfaced to us as `error_type: timeout` / HTTP 504.
3. **Streaming changes where the clock bites.** With `stream: true` OpenRouter
   *"sends you the HTTP 200 OK status and headers as soon as the provider accepts the
   request. That happens before the model produces a single token"*, and errors after that
   point arrive as mid-stream SSE events. A non-streaming request has no such early
   signal. ([Errors and Debugging](https://openrouter.ai/docs/api_reference/errors-and-debugging))
4. **Cache hits remove most of the prefill.** Prompt caching is automatic for DeepSeek,
   **cache reads cost 0.1× input**, cache writes cost 1.0× (no surcharge); OpenRouter keeps
   requests on the provider that warmed the cache **only if routing is sticky**
   ([Prompt Caching](https://openrouter.ai/docs/guides/best-practices/prompt-caching)).
5. **Sticky routing rules** (same page): granularity = account × model × conversation;
   default conversation key = hash of the first system message + first non-system
   message; sticky routing activates only *after* a cache hit is observed; sessions
   expire after **10 minutes of inactivity**; **`provider.order` disables sticky
   routing**; an explicit **`session_id`** (body field, or `x-session-id` header;
   ≤256 chars; body wins) activates stickiness from the *first successful request* and
   is also the reverse-compat path for `prompt_cache_key`.
6. **Usage is always reported.** `cached_tokens` / `cache_write_tokens` are in the
   `usage.prompt_tokens_details` of every response, including the final SSE chunk;
   `usage: {include:true}` and `stream_options.include_usage` are **deprecated and have
   no effect** ([Usage Accounting](https://openrouter.ai/docs/cookbook/administration/usage-accounting)).

### H2 — TESTED 2026-09-14, not supported (see §9 for the numbers)

`reasoning.effort` is **not** a lever on time-to-first-response here: n=3 per arm at 13.5k
input tokens gave first-chunk medians of 0.89 s (high) / 1.09 s (low) / 1.91 s (medium), and
the within-arm spread (low: 411 → 4,520 reasoning tokens) dwarfs the between-arm difference.
Pre-fill is not what makes the connection silent either — a 53.7k-token prompt at `high`
produced its first delta in 1.8-4.3 s. What *does* track the wall clock is hidden reasoning:
`reasoning_tokens` is 79-92% of output at every effort, and time-to-first-**content**
medianed 8-24 s, with a 41.6 s outlier in the *low* arm. So the effort knob keeps its
original, already-documented justification (output-budget starvation → empty report turns),
not a timeout one; the 504 is upstream provider behaviour, which is what the routing fixes
address.

### Ranked hypotheses for *this* 504 (each is cheaply testable — §6)

* **H1 — no cache, cold prefill on a slow host.** `session_id` is unset, so conversation
  identity is a hash of the first system+user messages; the analyst/trader prompts embed
  `Today's date is {current_date}` and `{instrument_context}` in the **system** message
  (`fundamentals_analyst.py:258-270`, `market_analyst.py:300-312`,
  `news_analyst.py:147-159`, `sentiment_analyst.py:165-175`), and the default load
  balancer picks the provider by price → high chance of landing on a host with no warm
  prefix. **Upgraded by the §W4 audit:** even with `session_id` stickiness the prefix is
  rebuilt every tool round, so the cache would stay cold anyway — H1 is now "sticky routing
  *and* the W4 fix are both required", not either/or.
* **H2 — reasoning `high` inflates time-to-first-*content*.** `.env:245` sets
  `reasoning.effort=high` globally; hidden reasoning is emitted before the answer. If the
  provider budget is measured to first response, the Trader terminal (largest prompt +
  high effort + `max_tokens=16000`) is the worst case.
* **H3 — the client's silent 504 retry storm.** The openai SDK retries any `>=500`
  (`_should_retry`, verbatim: 408, 409, 429, `>=500`) with our `max_retries=3`, and
  `structured.py:1044-1052` adds a free-text retry plus a backup-model continuation.
  A 504 at the Trader can therefore pay **up to 4 full re-prefills of the largest
  prompt** before falling back.

H1 and H3 are actionable with small, flag-guarded changes. H2 has one experiment (§6.3).

---

## 3. Workstreams

All OpenRouter request-body work lives in one place today:
`tradingagents/llm_clients/openai_client.py::OpenAIClient.get_llm` (existing knobs at
lines 347-354 `provider.ignore`, 356-367 `reasoning.effort`; helpers at 372-405). Keep it
that way — one `extra_body` dict, built once.

### W1 — Stream the response

**Change.** For `provider == "openrouter"`, add `streaming=True` to `llm_kwargs` when the
new flag is on. Do **not** add `stream_options`/`include_usage` (deprecated, no effect).

**Why it is the right lever.** With `streaming=True`, langchain-core 1.5.3
(`_should_use_protocol_streaming`) treats the instance attribute as affirmative and routes
`invoke()` through `_stream`, aggregating chunks into the same `ChatResult` — verified
against the installed `langchain-openai 1.4.1`. So every existing `chain.invoke(...)`,
`bind_tools(...)` loop and tool-call aggregation keeps working; only the wire format changes.

**Invariants / risks to preserve.**

* `with_structured_output(method="json_mode")` **pops `stream`** in `_generate`
  (`BaseChatOpenAI._generate`) → the json-mode path (graded judge, some validators) stays
  non-streaming. Document this; do not try to force it.
* `NormalizedChatOpenAI.invoke` normalizes the aggregated content — unchanged.
* `DeepSeekChatOpenAI._get_request_payload` re-attaches `reasoning_content`. With
  streaming, `reasoning_content` must survive chunk aggregation (langchain merges
  `additional_kwargs`); **must be asserted**, because dropping it re-introduces the
  DeepSeek 400 round-trip bug.
* Token accounting: `cli/stats_handler.py` sums `usage_metadata`. For non-default
  base URLs `stream_usage` defaults **off**; OpenRouter's final usage chunk still carries
  `usage`, and `_convert_chunk_to_generation_chunk` maps it whenever present — **but** it
  returns `None` when `choice["delta"] is None`. OpenRouter deviates from OpenAI by
  sending a **non-empty** `choices` array in the final usage chunk, so this should merge
  correctly — prove it empirically (§6.1). If usage is dropped, pass `stream_usage=True`
  (harmless) or read usage from a callback.
  **Resolved 2026-09-14 (live probe):** a streamed `invoke()` against OpenRouter returned
  `usage_metadata = {input_tokens: 6043, output_tokens: 27, input_token_details: {..., cache_read: 0}}`
  on turn 1 and `cache_read: 5888` on turn 2. No `stream_usage`/`stream_options` needed
  (the latter is deprecated on OpenRouter anyway), and the footer/index accounting sees
  both the tokens and the cache reads.

**Files.** `tradingagents/llm_clients/openai_client.py` (flag read + `llm_kwargs`),
`tradingagents/default_config.py` (`_ENV_OVERRIDES` + default), `.env.example`, docs.

**Tests.** Extend `tests/test_llm_client_timeout.py`'s capture pattern
(`_capture_openai_kwargs` monkeypatches the provider SPEC's `chat_class`):
assert `streaming is True` only for openrouter+flag, absent for native providers and for
openrouter+flag-off; assert `stream_options` is never added.

### W2 — Provider routing hardening

The pipe already exists: `extra_body["provider"] = {"ignore": [...]}` (line 354). Extend
the same dict (do not create a second one):

```python
provider = {"ignore": ignore}            # existing
provider["allow_fallbacks"] = allow_fallbacks   # default True — keep recovery
provider["sort"] = sort                  # "throughput" (or "latency")
provider["preferred_max_latency"] = ...  # seconds, optional
provider["preferred_min_throughput"] = ...  # tok/s, optional
provider["require_parameters"] = ...     # only hosts honoring max_tokens/tools
```

**Facts to encode in the docstring.** `sort`/`order` disable the default *price* load
balancing; `allow_fallbacks=true` keeps a failed host from failing the request;
`require_parameters=true` guarantees the host supports `tools`/`max_tokens` (the settings
the docs say OpenRouter already best-effort-filters on).

**Do NOT use `provider.order`** — the prompt-caching page states sticky routing is not
used when a manual order is specified, which would cancel W3. Prefer
`sort="throughput"` + the latency/throughput floors.

**Zero-code win — SHIPPED in `.env`.** Before the change
`TRADINGAGENTS_OPENROUTER_IGNORE_PROVIDERS` was empty while `.env.example:291` carried a
recommended slug list; the list is now live in `.env` (13 slugs, `openinference` dropped).
This is exactly the mitigation the user's note calls "provider routing preferences".

Checked against the live provider list (`GET https://openrouter.ai/api/v1/providers`, 106
slugs, fetched 2026-09-14): **13 of the 14 recommended slugs exist; `openinference` does
not** — drop it. Recommended value to set:
`morph,relace,decart,ambient,inceptron,parasail,wafer,mancer,sail-research,phala,venice,io-net,akashml`
(and refresh periodically; provider slugs churn).

**Tests.** Existing `test_openai_compatible_provider` (3 cases: present / omitted / not
openrouter): extend with sort+latency keys and a "never for non-openrouter" case.

### W3 — `session_id` sticky routing

**Change.** New config `openrouter_session_id` (env
`TRADINGAGENTS_OPENROUTER_SESSION_ID`). When unset, generate a per-client id:
`f"ta-{provider}-{model_slug}-{uuid4().hex[:16]}"` (≤256 chars, no PII, no key material),
cached on the client so every request from that client reuses it. Send as
`extra_body["session_id"]` (top-level body field; equivalent to the `x-session-id` header,
body wins).

**Why per-client is the right unit.** `batch.py:270` constructs a fresh
`TradingAgentsGraph` per symbol inside a worker, so one client =
one (symbol, run) unit of work — exactly the "chat thread / agent task" granularity the
docs prescribe. A cross-process env override stays available for nightly continuity.

**Constraints from the docs.** ≤256 chars; sticky TTL **10 minutes of inactivity**
(each successful request resets it); stickiness starts at the first *successful* request
(unlike the unfiltered default, which waits for an observed cache hit); sticky routing
never applies when `provider.order` is set (see W2).

**Non-goal.** Do not pass a per-call `session_id` through `invoke(**kwargs)`:
`BaseChatOpenAI._get_request_payload` merges kwargs into the payload, which is then splatted
into `client.chat.completions.create(**payload)` — an unknown top-level key raises
`TypeError`. `extra_body` at construction (or a `_get_request_payload` override, the
MiniMax/DeepSeek precedent at `openai_client.py:155-161`) are the only safe routes.

**Tests.** Payload carries a top-level `session_id` under `extra_body`; env override wins;
length ≤256; not emitted for other providers; two clients get different ids, one client
reuses its id across two `get_llm()` calls.

### W4 — Prefix-cache stability — **CONFIRMED DEFECT in the normal path** (highest ROI here)

Audited by reading the router + the analyst nodes + `evidence_gather`. Result: the plan's
original assumption ("the good-path request is append-only") is **wrong for the analyst tool
loops**, and the break is at **token 0**, not mid-history.

**Mechanism (VERIFIED).**

1. The analyst tool loop re-enters the analyst node every round
   (`conditional_logic.py:39-84` routes `analyst → tools_*` while
   `tool_rounds < MAX_TOOL_ROUNDS`, and `tools_* → analyst` after each tool round).
2. Every entry of the node calls `gather_for_analyst_node`
   (`market_analyst.py:33-35`; same at the top of the news/fundamentals nodes).
3. On re-entry the gather short-circuits to a **re-render** from accumulated state:
   `evidence_gather.py:471-474` → `_render_evidence(existing[analyst_key], pool,
   reference_line=…)` — note the **missing `notes=`** that the first render carries
   (`evidence_gather.py:576-578`, `notes=move_notes`; consumed at `:424-427`, where
   `if notes:` appends the "## Declared-default tools moved to the deterministic gather"
   section). `_render_evidence` (`:407-431`) applies **no size cap** — it concatenates
   every leaf, so the block only ever grows.
4. That rendered block is partialed into the **system message**, i.e. `messages[0]`
   (`market_analyst.py:300-312` and siblings).

So `messages[0]` differs between round 1 and round 2+ (the notes section disappears), and
grows again every time the LLM calls a tool of its own (each such call appends an evidence
leaf at `evidence_gather.py:826-832`, which the next re-entry renders back into the system
message). **Consequence: the cached prefix is invalidated from token 0 on every tool round**, so
every round pays a full cold prefill of the largest prompt in the stack — the exact cost
that produces the 504-class failure and the TTFT spikes.

**Fix options, cheapest first.**

* **F1 (smallest diff):** make the re-render byte-identical to the first render — persist the
  first-rendered block (and its `notes`) in state and return it verbatim on re-entry. Cache hits
  then survive, but the block still grows on LLM-called tools → still a mid-prefix break.
* **F2 (correct):** stop putting the growing evidence block in the prefix at all. Render the
  forced-evidence block **once** (round 1) into a message that never changes, and append
  subsequently-gathered leaves as a **new trailing message** (human/tool) instead of
  re-rendering `messages[0]`. This is the documented rule: *append volatile/growing content at
  the tail, never in the prefix.*
* **F3:** if the block must stay live, mark the boundary explicitly instead of relying on
  implicit prefix matching (only meaningful for explicit-cache providers — not DeepSeek).

**Invariant to pin (test).** For one analyst, capture the outgoing message array on two
consecutive tool rounds and assert the byte prefix up to the first appended element is
unchanged. Today that test fails at index 0 — write it first, quantify the damage, then fix.

**Also verified, lower priority (once per analyst per run, not per round).** The cap-forced
terminal turn rewrites already-sent history: `finalize_messages` replaces the last message and
`_deorphan_tool_calls` (`structured.py:818-824`, `:831`, `:615-678`) strips unfulfilled tool
calls from *earlier* turns. That is once per analyst, and the rewrite is required for the
strict-backend 400 it fixes (`CHANGELOG.md:1325-1337`) — so keep it, but note it as a stated
full-prefix miss on the final turn. **Do not "fix" it by dropping the guard.**

**Checked and refuted (do not re-litigate).** A first-pass audit claimed the analyst nodes take
the `finalize_messages` branch on *every* tool round (which would double every round's cost).
The router refutes it: `conditional_logic.py:39-84` sends the state to the tool node while
`tool_rounds < 8` and back to the analyst node **only at the cap** — so that branch is reached
once per analyst per run, exactly as its comments state. The per-round cost here is the
system-message re-render above, not an extra terminal call.

**Volatile `current_date` / `instrument_context` in the system message**
(`fundamentals_analyst.py:259`, `market_analyst.py:301`, `news_analyst.py:148`,
`sentiment_analyst.py:166`) is a real but secondary issue: constant within a run, so it costs
cross-run (and cross-batch) reuse only. Rule to adopt: **volatile values go in the last user
message; the system prefix is byte-stable for a given (agent, provider, model).**

**Cross-analyst reuse is structurally zero.** `create_msg_delete`
(`agent_utils.py:662-679`, wired at `setup.py:298`) empties the messages channel between
analysts, so each analyst re-prefills its own system+placeholder prefix. That is by design;
with 4 analysts it is 4 cold prefixes per run — relevant when sizing W5, not a bug.

**Block boundaries.** DeepSeek caching is implicit/engine-side; padding to 16/64-token blocks
is an optional refinement for the largest static block, only worth doing after W7 shows a
partial-block miss.

**Determinism (audited — no change needed).** The tools array is a hand-written list literal
per analyst (`toolsets.py:222-341` market, `:343-374` news, `:376-432`/`:434-459`
fundamentals), the `analyst_toolset` union dedupe is order-preserving (`_dedupe`,
`toolsets.py:462-472`, `set` used for membership only), the model pool is emitted `sorted(...)`
and the gather pool in spec order (`evidence_gather.py:258-259`, `:396-400`), `{tool_names}` is
built from that same list object (`market_analyst.py:310` vs `:314`), and no tool schema
carries volatile content (no `args_schema=`/`from_function`/dynamic `__doc__=` anywhere under
`agents/`). So the ordering half of the prefix is deterministic, and W4 needs **no** sort step.
One latent trap: `parse_forced_spec` returns `list(registered_names)` for an `ALL` spec
(`evidence_gather.py:78-79`) where the caller passes a `set` (`:500`) — unreachable today only
because `gather_for_analyst_node` intercepts `ALL` earlier (`:505-507`). If that interception
ever moves, the tool order (and the whole prefix) becomes set-iteration dependent; leave a
comment on both sides.

**Cross-run byte-identity does not hold, and should not be aimed for.** The evidence block
carries live vendor output and a reference-price line (`_reference_price_line` →
`price_consistency.py:77-100`), and some tool bodies call `datetime.now()` for their windows
(`analysis_tools.py:55`, `:4182`, `:6219`, `:6247`). Same template, different bytes — fine, as
long as the *within-run* loop is stable (the W4 fix).

### W5 — Cut the prompt that 504s (separate plan, listed for completeness)

Absolute prefill time scales with prompt tokens. **Measured static-prefix size** (AST
string-literal scan of the analyst modules + `json.dumps` of each bound tool's
`args_schema` and description; token figures are `chars/4` estimates, labelled as such):

| Agent | bound tools | tool schema+desc chars | tool prose chars | static prefix (est. tokens) |
|---|---|---|---|---|
| market | **115** | 151,402 | 39,611 | **~48k** |
| fundamentals | 52 | 76,262 | 24,264 | ~25k |
| news | 27 | 35,706 | 13,214 | ~12k |
| sentiment | 0 (tool-less) | — | 8,177 | ~2k |

Two of those numbers are the same information twice: the analyst system prompt contains a
hand-written paragraph for essentially every tool the API already sends in `tools[]`. The
market analyst ships **115 tools** — an order of magnitude past the point where tool choice
starts degrading, and the single largest lever on prefill time.

**And with `.env:189` (=`ALL`) the evidence block is sized by the gather pool**
(`classify_tool_pools` run locally against the real toolsets + `TOOL_ARG_DEFAULTS`):

| Agent | bound | gathered deterministically | model pool | evidence-block ceiling (gathered × 12,000 chars) |
|---|---|---|---|---|
| market | 115 | **87** | 28 | 1,044,000 chars ≈ 261k tokens |
| fundamentals | 52 | 43 | 9 | 516,000 chars ≈ 129k tokens |
| news | 27 | 24 | 3 | 288,000 chars ≈ 72k tokens |

Those are *ceilings* (each leaf is truncated at `summary_window`, real vendor payloads are
usually shorter), and `_render_evidence` applies no cap of its own (`evidence_gather.py:407-431`)
— so the block is bounded only by 87 tool outputs. Combined with W4 (re-rendered into the
prefix every round) this is the mechanism behind the measured 33,242-token analyst prompt and
the terminal-stage prefill that times out.

Ranked candidates:

1. **Collapse the prose tool catalog.** Either delete the duplicated paragraphs or derive a
   one-line index from the schema at build time. Highest value; must be quality-gated
   (`scripts/context_ab.py` exists for exactly this).
2. **Trim the bound tool surface** (115 → the gather-pool + a shortlist). The repo already
   has the machinery to classify pools (`evidence_gather.classify_tool_pools`) and an
   escape hatch for model-judgment tools (`analyst_tools_model_supplied`).
3. **`{evidence_block}`**: `TRADINGAGENTS_ANALYST_FORCED_TOOLS=ALL` (`.env:189`) with
   `summary_window=12000` chars per tool (`evidence_gather.py:170`) — bound the block
   (top-N by relevance, or a per-tool cap below 12k) and note that W4's fix is what stops
   it from being re-rendered into the prefix every round.
4. **Analyst reports re-sent verbatim to the debate stages — MEASURED 2026-09-14, once
   implemented, before deleting** (details in §9). Correcting this plan's own wording: the
   *terminal* stages do NOT carry the reports — `trader.py:57-84` takes only
   `investment_plan` + `computed_decision_context`. The verbatim copies live in the two
   researchers (`bull_researcher.py:43-46`, `bear_researcher.py:45-48`) and the three risk
   debators (`aggressive/conservative/neutral_debator.py:38-41`), which is 5 prompts per
   `--depth shallow` run and 2 + 3×depth prompts at depth N. On a paired 16-item harness the
   best digest (headings + first sentence per section + a label→figures ledger) cut the
   prompt **45%** (8,204 → 4,530 input tokens) with **no fabrication penalty** (fabricated
   figures 21 → 10 across pairs; worse in 3 pairs, better in 9, equal in 4) but the answer
   cited **29% fewer distinct figures**. Viable, not free — and not needed for the timeout
   fix: this is a cost/latency lever on the smallest prompts in the stack, not the prefill
   that timed out. Recommendation: do not ship it without an end-to-end A/B scored by the
   repo's own gates; prioritise items 1-3 above (analyst-side prefix), which are paid on
   every round.

Out of scope here: RAG/chunking of the static docs — the change with the highest blast
radius on report quality; treat it as its own A/B.

### W6 — Failure semantics: typed 504 + retry amplification

**Observed.** SDK retries `>=500` with `max_retries=3` (`.env:90`), then
`structured.py:1044-1052` retries as free text, then the backup model
(`TRADINGAGENTS_BACKUP_LLM=openrouter:openai/gpt-5.6-luna`, `.env:193`) continues — up to 4
prefills of the largest prompt per logical failure.

**Change.**

* Detect the typed error (`code == 504` / `metadata.error_type == "timeout"`) wherever the
  openai SDK error surfaces, and journal it as a first-class field (`error_type`, `code`,
  `model`, `session_id`) instead of only `str(exc)` — today
  `llm_failure_journal.journal_llm_failure` stores `message = str(exc)`, which is how the
  one 504 record is even readable.
* ~~When the flag is on: on a typed timeout, drop the provider that timed out for the rest
  of the run.~~ **Deferred, and the flag was not shipped as a no-op.** The typed error body
  carries `error.metadata.provider_code` (the provider's own error code), not the provider
  slug, and the routing context (`openrouter_metadata`) only comes back when the request
  opts in with `X-OpenRouter-Metadata` — unverified. Dropping "the provider" therefore means
  dropping nothing, or dropping the wrong one. The honest interim: the typed field is
  journaled (`error_type: timeout` + `provider_code`), so the offending host is identifiable
  per occurrence from `FailureLog/`, and the routing knobs above (sort/latency floor +
  the blocklist) can be tightened from that evidence. Revisit with a
  `provider_code → slug` mapping or the metadata header verified against a live 504.

**Non-goal.** Do not lower `request_timeout` below OpenRouter's own provider budget: our
client timeout is not the binding constraint today, and lowering it converts a provider
504 into a worse client-side abort.

### W7 — Cache telemetry (do this first)

`langchain-openai` maps `prompt_tokens_details.cached_tokens` →
`usage_metadata["input_token_details"]["cache_read"]` (and `cache_write_tokens` →
`"cache_creation"`); confirmed in the installed source. For OpenRouter the final chunk is
non-empty-choices, so the existing `cli/stats_handler.py` aggregation path should see it.

**Change.**

* `cli/stats_handler.py`: accumulate `input_token_details.get("cache_read", 0)` and
  `cache_creation`; print them in the footer (`cache: 44.8k/45.1k read`). **Read the
  service-tier-prefixed keys too** (`priority_cache_read` / `flex_cache_read`): langchain's
  `_create_usage_metadata` prefixes both cache keys with the tier whenever the response
  carries one (verified in the installed `langchain-openai 1.4.1`), so a `:nitro`/priority
  route silently moves the number to a key a plain `cache_read` lookup misses.
* `llm_failure_journal` + the `structured.py` cap-forced note: record `cache_read`,
  `input_tokens`, `session_id`, `provider` slug if surfaced via response metadata
  (`X-OpenRouter-*` headers / router metadata opt-in).
* `tradingagents/strategies/llm_cost.py`: the rate table prices input at full rate; cache
  reads are 0.1× for DeepSeek. Either add a `cached_input_tokens` parameter or state the
  omission in the docstring — an under-counting estimate is worse than a labelled one.

**Acceptance signal.** Two consecutive turns of one agent in one run show
`cache_read > 0` and rising with turn index.

---

## 4. Config keys (new)

| Env (`TRADINGAGENTS_…`) | Config key | Default | Notes |
|---|---|---|---|
| `OPENROUTER_STREAMING` | `openrouter_streaming` | `` (off) | `true` ⇒ `streaming=True` for openrouter only |
| `OPENROUTER_SESSION_ID` | `openrouter_session_id` | `` | `auto` ⇒ per-client `ta-…-<uuid16>`; a literal pins a named session; empty ⇒ no key sent (≤256 chars, enforced) |
| `OPENROUTER_PROVIDER_SORT` | `openrouter_provider_sort` | `` | `throughput` \| `latency` \| `price`; empty ⇒ OpenRouter default price balancing |
| `OPENROUTER_PREFERRED_MAX_LATENCY` | `openrouter_preferred_max_latency` | `` | seconds |
| `OPENROUTER_PREFERRED_MIN_THROUGHPUT` | `openrouter_preferred_min_throughput` | `` | tok/s |
| `OPENROUTER_REQUIRE_PARAMETERS` | `openrouter_require_parameters` | `` | `true` ⇒ only hosts honoring tools/max_tokens |
| `OPENROUTER_ALLOW_FALLBACKS` | `openrouter_allow_fallbacks` | `` | empty ⇒ omit (OpenRouter default `true`) |


Register each in `default_config._ENV_OVERRIDES` (lines 10-210 block) + `DEFAULT_CONFIG`
(next to `openrouter_ignore_providers` / `openrouter_reasoning_effort`, lines 476-486),
and mirror in `.env.example`, `docs/api_reference.md` (env table),
`docs/AGENT_ONBOARDING.md`, `README.md` changelog line, `CHANGELOG.md`.

---

## 5. Rollout & acceptance criteria

1. **W7 + W6-telemetry** always on — establishes the baseline numbers
   (`input_tokens`, `cache_read`, `session_id`, timeout count) in the journal and footer.
2. **W2 (ignore list only, no code)** in `.env` — immediate, reversible.
3. **W1+W2+W3** behind one flag; A/B on one ticker that reproduces a large-prompt stage.
4. **W4** fix the confirmed prefix defect (F1/F2 in §W4), with the two-round invariant test
   written first so the fix is measurable.
5. **W5** as its own plan with its own A/B (report-quality gate).

Acceptance for the batch as a whole:

* zero `error_type: timeout` journal entries across a full nightly batch;
* `cache_read > 0` on the second and later calls of each agent's tool loop;
* total prompt tokens billed at the cached rate for ≥50% of input tokens on the Trader/RM/PM
  stages;
* no regression in the report/JSON parse classes (`structured output returned no parsed
  result`, length-limit empties) — those are the dominant failures and must not grow;
* `ToolCallLog/` and the token footer still report input/output tokens (streaming did not
  drop `usage_metadata`).

---

## 6. Verification

### 6.1 Unit (mirror `tests/test_llm_client_timeout.py`)

The capture helper monkeypatches the provider SPEC's `chat_class`
(`monkeypatch.setitem(omod.OPENAI_COMPATIBLE_PROVIDERS, "openrouter", ProviderSpec(chat_class=_fake))`)
so construction kwargs are inspectable. Add:

* `streaming` present iff provider=openrouter ∧ flag; `stream_options` never present;
* `extra_body.provider` carries unchanged `ignore` + new sort/latency keys together
  (regression: the sort keys must not overwrite `ignore`);
* `extra_body.session_id` stable across two `get_llm()` calls on one client, distinct
  across two clients, env override wins, ≤256 chars;
* non-openrouter providers get **no** `session_id`/`provider`/`streaming`.

### 6.2 Live probes (throwaway scripts, not committed tests)

1. **Streaming + usage survives.** One streamed `invoke()` against OpenRouter with a
   ~5k-token prompt: assert `response.usage_metadata` is non-None and
   `input_token_details` present. (Guards the `choice["delta"] is None` drop noted in W1.)
2. **Cache hit.** Two identical requests with the same `session_id`, second one issued
   within the 10-minute TTL: assert `cache_read > 0` on the second and that both landed on
   the same provider (via `X-OpenRouter-*`/router metadata or the `/generation` endpoint).
3. **H2 experiment.** Re-run the failing stage with `reasoning.effort` `high` vs `medium`
   vs `low` and compare time-to-first-chunk and 504 incidence. Keep `high` only if it is
   not the time-to-first-response driver.
4. **Large-prompt probe.** A single request at ~40-60k prompt tokens (the Trader-terminal
   shape) with/without W1+W2+W3, measuring TTFT and outcome.

### 6.3 Non-regression

* Full `pytest` (the repo's suite is large; run once at the end of the change, not
  mid-flight).
* One real end-to-end run on a symbol from the failing batch (the 16:10 entry was a live
  batch run) and diff the report tree against the previous run for the parser classes.

---

## 7. Rejected alternatives / non-goals

* **`provider.order`** — disables sticky routing (prompt-caching docs), cancelling W3.
* **`:nitro` / `:floor` model suffixes** — would sort/disable balancing as desired, but the
  suffix is part of the model id, which this repo keys capability lookups
  (`capabilities.get_capabilities`), validation (`validators.validate_model`) and cost
  (`strategies/llm_cost` rate table) on. If wanted, it needs an id-normalization step
  first; not in this plan.
* **Anthropic-style `cache_control` breakpoints** — only meaningful for explicit-cache
  providers (Anthropic, Alibaba Qwen, Gemini); DeepSeek caching is implicit. If the model
  is ever repinned to one of those, add the breakpoints *then*; keep W4's layout rules
  regardless (they are the same rule).
* **RAG/chunking the static context** — highest blast radius on report quality; own A/B.
* **Raising `request_timeout`** — the binding timer is upstream, not ours.

---

## 8. Open questions

1. Does OpenRouter's provider response budget count time-to-first-**chunk** (including
   reasoning deltas) or time-to-first-**content** token? Determines whether H2
   (`reasoning.effort=high`) is a lever for the 504 or only for the length-limit class.
2. Exact `usage`-chunk shape when `streaming=True` through langchain 1.4.1 (delta empty vs
   `None`) — resolved by probe 6.2.1.
3. Whether the deterministic `evidence_block` and the in-prompt tool catalog can be
   trimmed without moving the citation-discipline scores in the repo's own harnesses
   (`scripts/context_ab.py`) — W5's gate.

---

## 9. Delivery status

**Shipped 2026-09-14.**

| Item | Where |
|---|---|
| W4 fix (frozen first-rendered block) | `agents/utils/evidence_gather.py` — `RENDERED_BLOCK_KEY`, `_frozen_block`, `_with_frozen_block`; first render frozen at `gather_for_analyst_node`, re-served verbatim on every re-entry |
| W1 streaming | `llm_clients/openai_client.py::_openrouter_streaming` → `llm_kwargs["streaming"]` |
| W3 sticky session | `_openrouter_session_id` (`auto` sentinel) → `extra_body["session_id"]` |
| W2 routing prefs | `_openrouter_provider_prefs` (sort / latency / throughput / require_parameters / allow_fallbacks, merged with `ignore`) |
| W7 telemetry | `cli/stats_handler.py` (`tokens_cached`, `tokens_cache_write`, tier-prefixed keys), `cli/main.py` footer `(cache N)`, `strategies/llm_cost.py` (`cache_read_multiplier` + `cached_input_tokens`) |
| W6 telemetry | `agents/utils/llm_failure_journal.py` (`_provider_error_fields`, `_usage_fields`, `provider`/`session_id`) |
| Config | `default_config.py` (`_ENV_OVERRIDES` + defaults), `.env.example`, `docs/api_reference.md`, `.env` (`STREAMING=true`, `SESSION_ID=auto`, blocklist) |
| Tests | `tests/test_llm_client_timeout.py` +8, `tests/test_evidence_gather.py` +2 |

**Verification done:** full `pytest tests` — **4224 passed, 5 skipped** (all five skips
pre-existing: optional `langchain_aws` absent, no live DeepSeek key, two empty parameter
sets), run with `TRADINGAGENTS_ANALYST_FORCED_TOOLS` cleared and `--timeout=600` so the
suite stays hermetic (see the caveat below); the live two-turn probe (§0 result table); and
the W4 regression test was checked to *fail* against the pre-fix code path (confirmed: the
old re-render differs from the round-1 block and leaks the leaf journaled between the two
rounds).

**One pre-existing suite caveat, unrelated to this change but worth knowing before you run
`pytest tests`.** `tradingagents/__init__.py` loads `.env` at import, so the suite inherits
`TRADINGAGENTS_ANALYST_FORCED_TOOLS=ALL` from this repo's `.env` — and the "hermetic" graph
test `tests/test_debate_stream_hermetic.py` then performs the real ~87-tool vendor gather
inside a module marked `pytest.mark.timeout(120)`. Measured: **125.1s with `.env`'s `ALL`,
7.2s with the variable cleared** — i.e. it is the live gather, not this change (the gather
path is otherwise untouched, and the freeze only *removes* work on a re-entry, of which this
test has none). Run the suite with `TRADINGAGENTS_ANALYST_FORCED_TOOLS=` or a raised
`--timeout` if you want it green.

**Batch A/B (rollout step 4/5), run 2026-09-14 on SKHY — PASSED.**

| arm | code/config | outcome | wall | journal entries during the run |
|---|---|---|---|---|
| before | pre-change code + config, `batch.py --symbols SKHY --depth shallow` at 15:42 | **FAILED** — `ValueError({'message': 'The operation was aborted', 'code': 504, 'metadata': {'error_type': 'timeout'}})` | n/a (no tree) | 1 (`structured/Trader`, 16:10) |
| after | this change (`STREAMING=true`, `SESSION_ID=auto`, blocklist live), same command at 17:17 | **Hold** — full tree written (`complete_report.md` 63.7 kB, 16 reports, `run_card.json` `decision.verdict=PASS`, `debate.degraded=false`) | 1785 s | **0** |

Context for the "before" arm: every symbol in both of that afternoon's batches failed the same way (4/4 at 15:08, 2/2 at 15:42), so the baseline is not a single unlucky run.

Production evidence that the W4 freeze is live (from the after run's `tool_evidence.json`): `_rendered_block` carries 3 rows (market/news/fundamentals) alongside `_model_pool` and `_symmetry` — the reserved rows are invisible to the report walkers, and the run wrote a complete tree with them present. The frozen prefix each analyst now re-serves: fundamentals 59,107 chars (~14.8k tokens), market 34,449 (~8.6k), news 32,204 (~8.1k). Gathered leaves: market 95, fundamentals 44, news 29.

Caveat, stated rather than buried: this is a same-day before/after, not a controlled two-arm experiment (a true "before" arm would need the code reverted). The wall time is dominated by the deterministic gather (87 tools, `max_parallel=1`), not prefill — this change targets the timeout class, and W5 is the lever for absolute duration.

**Experiments closed 2026-09-14 (both items the plan left open).**

*H2 — `reasoning.effort` vs time-to-first-response: not supported.* Paired arms on the real
prompt shape (13.5k input tokens, the four SKHY analyst reports), n=3 per arm, streaming:
first-chunk medians 0.89 s (high) / 1.09 s (low) / 1.91 s (medium); a 53.7k-token prompt at
`high` still produced its first delta in 1.8-4.3 s. Within-arm spread dwarfs the between-arm
difference (the `low` arm burned 411 → 4,520 reasoning tokens). Hidden reasoning is 79-92% of
output at *every* effort and time-to-first-**content** medianed 8-24 s (one 41.6 s outlier in
the low arm), so the knob's justification stays the documented output-budget one, not a
timeout one. Raw rows: `reports/experiments_20260914/_effort_ab.json` (gitignored).

*W5 item 4 — debate-stage report digest: viable, not free, not needed for the timeout fix.*
Throwaway paired harness over the 38 archived report trees (`~/.tradingagents/logs/*/*/reports`),
8 sets × 2 debate questions = 16 pairs, condition A = reports verbatim, condition B = a
recall-preserving digest (headings + first sentence per section + label→figures ledger,
55% smaller, 91% of distinct figures retained), scored deterministically: a figure in the
answer that appears in no report counts as fabricated (same extraction both arms).

| metric (median) | A verbatim | B digest |
|---|---|---|
| prompt input tokens | 8,204 | **4,530 (-45%)** |
| fabricated figures (total across pairs) | 21 | **10** |
| grounded figures cited | 39 | 28 (-29%) |

A first variant that deduped figures (57% cut, 74% recall) behaved the same way, so the
recall gap is not what costs the citations — dropping the prose is. Caveats: synthetic
single-turn harness, one model/route, deterministic figure matching as the *only* quality
proxy (no downstream decision-quality gate), one report corpus. Raw rows:
`reports/experiments_20260914/_digest_ab.json` (first variant) and `_digest_ab_v3.json`. Next step if wanted: an
end-to-end A/B on one symbol with the digest behind a flag, scored by `report_verify`
GROUNDED rate + decision stability. **Recommendation: not worth shipping ahead of W5 items
1-3**, which are prefix costs paid on every round.

**Still open, with owners:**

1. **W5 items 1-3 (analyst-side prefix)** — the only remaining lever on absolute prefill
   time, and the one that is paid on every round: 115 bound tools for the market analyst
   (~48k-token static prefix: tool schema + the hand-written prose catalog that restates it)
   plus the `_ALL` evidence block (87 gathered tools, `summary_window=12000` per leaf, no cap
   in `_render_evidence`). Needs its own quality-gated A/B (`scripts/context_ab.py`).
2. **W5 item 4 (debate-stage digest)** — measured, viable, not recommended yet: see the
   experiment note above. Ship only behind an end-to-end A/B.
3. **W6 provider rotation** — deferred with its reason recorded in §W6 (no reliable slug in
   the error payload). The typed fields now in the journal are the evidence needed to
   build it.
4. **`PROVIDER_SORT`** stays empty in `.env` on purpose (`throughput` disables price
   balancing and can raise cost). Nothing measured argues it is needed after the routing
   blocklist + streaming landed.

**Rollback:** every knob is config-level. `TRADINGAGENTS_OPENROUTER_STREAMING=` and
`TRADINGAGENTS_OPENROUTER_SESSION_ID=` restore the previous request body exactly (both
default to off in `DEFAULT_CONFIG`); the W4 freeze is behavior-compatible by design — the
model still sees every tool result in the transcript and `tool_evidence` still carries every
leaf, so only the prompt prefix stops moving.
