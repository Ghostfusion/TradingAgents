# 10. Tests layout map

Quick orientation to the `tests/` directory — what each file covers, how
fixtures work, and how to run. This is the equivalent of `01-topology.md` but
for tests: know which file guards which module before you edit.

## File count & categories

**404 `test_*.py` files** (plus `__init__.py`, `conftest.py`, `prompt_text.py`
= 407 `.py` in the directory). They break into domains by naming convention.
The counts below are measured glob counts on 2026-10-01 and are per-glob, so a
file matching two patterns is counted twice; the total is the 404 above.

| Group | Convention | Count | Guards |
| --- | --- | --- | --- |
| Strategy calculators | `test_*strategies*` | 42 | every `strategies/*` pure function (incl. `test_strategies_value_dip.py`, `test_strategies_pre_market.py`, `test_strategies_ratios.py`, `test_strategies_market_session.py`) |
| Dataflow / vendors | `test_*vendor*, test_*moomoo*, test_*finnhub*, test_*fred*, test_*fmp*, test_*polymarket*, test_*alpaca*, test_*alpha*, test_dataflows_config, test_symbol*, test_*reddit*, test_stocktwits*, test_*short*, test_*float*` | 15 for `test_*vendor*`; the rest of the family is named individually | routing / errors / cache / symbol map |
| Graph / wiring | `test_*wiring*` (13), `test_*routing*` (3), `test_*analyst*` (8), plus `test_*execution*, test_*parallel*, test_*checkpoint*, test_*signal*, test_*toolnode*, test_*instrument*, test_*ticker*, test_*crypto*, test_*i18n*, test_news_lookahead` | 13 / 3 / 8 | graph edges, state, i18n, tool nodes |
| LLM / providers | `test_*provider*` (4), `test_*prompt*` (6), `test_*tool*` (8), plus `test_*api_key*, test_*openai*, test_*anthropic*, test_*google*, test_*bedrock*, test_*ollama*, test_*model*, test_*reasoning*, test_*temperature*, test_*retries*, test_*minimax*, test_*deepseek*, test_capabilities` | 4 / 6 / 8 | factory, model select, key precedence |
| Repo-wide gates | `test_*contract*` (14), `test_*gate*` (7), `test_*score*` (23) | 14 / 7 / 23 | see the gate list below |
| Scripts / screener | `test_value_screener, test_scan_*, test_sector_*, test_*growth_*, test_*config_gate, test_*orderflow_evaluate, test_*stress*, test_action_report` | named individually | screens, scans, eval scripts, conditional action report |
| Smoke / misc | `test_reporting, test_pipeline, test_batch_*, test_cli_*, test_memory_log, test_news_lookahead`, etc. | remainder | reports, batch, CLI flags |

**Repo-wide gate tests** (contracts, not single features) — a change that
ignores one of these fails the suite: `test_calc_agent_wiring`,
`test_dead_state_dedupe`, `test_doc_binding_claims`,
`test_prompt_signature_contract`, `test_prompt_trigger_contract`,
`test_test_quality_gate`, `test_execution_contract`,
`test_config_isolation`, `test_gate_env_toggles`,
`test_api_reference_env_table`, `test_tool_binding_single_source`,
`test_vendor_signature_contract`, `test_window_integrity`,
`test_report_hygiene`, `test_engine_ownership_map`.

The **Massive** integration has two dedicated files:
- `tests/test_massive_vendor.py` — new REST endpoints (news sentiment, economy,
  short interest/volume, form-4, ratios, snapshots, movers, dividends/splits,
  related-companies, IPOs), all HTTP mocked.
- `tests/test_massive_flat_noi.py` — the Flat-File loader + NOI monitor + the
  screener flat-folder seam + the validator.

## Marker conventions

- `@pytest.mark.unit` — pure/offline; no network (dominant).
- `@pytest.mark.integration` — one file uses it (live-ish, key-gated).
- `@pytest.mark.skipif` — used for optional deps (e.g. bedrock needs
  langchain_aws) and live DeepSeek when the key is absent.
- `@pytest.mark.parametrize` — used 26x for table-driven units.

## Fixtures (`conftest.py`, autouse)

- `_dummy_api_keys` — fills every provider key env var with a placeholder so
  tests never hit real APIs (unless the test explicitly sets a real key).
- `_isolate_config` — calls `reset_config()` + clears the vendor cache before
  and after each test, so a prior test's `set_config`/mocked vendor result can't
  leak into the next (order-independent tests). `reset_config()` restores
  `SHIPPED_DEFAULTS`, **not** the ambient `DEFAULT_CONFIG`, so this machine's
  `.env` gates never reach a test — a developer with the run-card engines
  enabled used to make every `write_report_tree` in `test_reporting.py` fetch a
  nine-name peer universe (two 30-minute bounds, fixed 2026-09-30; see
  `tests/test_config_isolation.py`). Also closes moomoo contexts
  (`_close_all_ctxs`) to avoid process hang.
- `_isolate_forensics` — points `llm_failure_journal_dir` and `tool_call_log_dir`
  at a `tmp_path_factory` temp dir, so a failed end-to-end test cannot append to
  the operator's real journals.
- `_disable_reddit_killswitch` — removes `TRADINGAGENTS_DISABLE_REDDIT` so the
  fetcher's real path runs even if a local `.env` opts out.
- `_mock_computed_sentiment` — patches `sentiment.compute_social_scores` to
  `None`, so no test reaches live StockTwits.
- `mock_llm_client` (not autouse) — patches `factory.create_llm_client` with a
  `MagicMock` for structured-agent tests.

## How to run

```bash
# one file
py -3.12 -m pytest tests/test_strategies_swing.py -q --no-header -p no:cacheprovider
# one test
py -3.12 -m pytest tests/test_strategies_swing.py::test_some_name -s
# a domain
py -3.12 -m pytest tests/test_strategies_*.py -q --no-header -p no:cacheprovider
# whole suite (~15 min; 6,286 tests; includes slow value_screener / LLM-mock tests)
py -3.12 -m pytest tests/ -q --no-header -p no:cacheprovider
```

Use `py -3.12` (bare `python` has no pytest).

## Test timers (required)

Every test inherits a per-test deadline so a hung vendor / network call can never
block the whole session indefinitely (``pytest-timeout``):

- **Global default: 180 s per test, thread method** — set in
  ``[tool.pytest.ini_options]`` (``timeout`` / ``timeout_method``). The thread
  method is the only one reliable on Windows (signal timers are POSIX-only).
- **Module-level override: ``pytestmark = pytest.mark.timeout(N)``.** **176 of
  the 404** test modules carry one (values 30-600 s). It exists for modules whose
  tests legitimately run live vendor calls end-to-end
  (``test_value_screener``, ``test_scan_strategies``, ``test_growth_screens``,
  ``test_structured_agents``) — those measured 12-62s per test on a normal
  network, so 180s would be too tight on a slow one. Examples:
  ``tests/test_config_isolation.py:21`` → 600, ``tests/test_execution_contract.py:24``
  → 120, ``tests/test_alpha_zoo.py:8`` → 30.
- **Session cap: 30 min** (``session_timeout = "1800"``) — checked between
  tests, never interrupts a test in progress; a long chain of slow network tests
  can't keep a CI/dev session open forever.

New tests should stay well under 180s; only add a module-level marker when the
module genuinely runs minutes of live vendor calls. pytest-timeout itself is a
dev dependency (``pip install -e .[dev]`` / it is already in the py3.12 env).

## Hermetic-testing habit that matters

- **Mock the network**, never call real vendors in unit tests. `mock.patch`
  `route_to_vendor`, `_get`, or `requests.get` etc.
- **Offline strategy tests** just import the pure `strategies/*` function and
  feed synthetic input.
- For a new Massive endpoint: `mock.patch.object(massive, "_get", ...)` (the
  `_get` helper is the single network seam for Massive) — see
  `tests/test_massive_vendor.py`.
- For a new vendor: feed the router a fake vendor impl or patch the vendor
  module's network function.

## Running the full suite

`py -3.12 -m pytest tests/ -q --no-header -p no:cacheprovider` — expect a handful
of skips (bedrock extra, live DeepSeek key) and occasionally a couple of
network-flaky yfinance-sector tests that fail only when hyper-offline.

## Related

- Developer dev-guide: `08-development.md` (§8.3 run/test, §8.6 testing conv.)
- Project tests wiring: `graph/trading_graph.py` docstring + `tests/conftest.py`