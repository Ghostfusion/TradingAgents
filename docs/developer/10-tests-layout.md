# 10. Tests layout map

Quick orientation to the `tests/` directory — what each file covers, how
fixtures work, and how to run. This is the equivalent of `01-topology.md` but
for tests: know which file guards which module before you edit.

## File count & categories

~100 `test_*.py` files (plus `__init__.py` + `conftest.py`). They break into
five domains by naming convention:

| Group | Convention | Approx count | Guards |
| --- | --- | --- | --- |
| Strategy calculators | `test_strategies_*.py` | 20 | every `strategies/*` pure function |
| Dataflow / vendors | `test_*vendor*, test_*moomoo*, test_*finnhub*, test_*fred*, test_*fmp*, test_*polymarket*, test_*alpaca*, test_*alpha*, test_dataflows_config, test_symbol*, test_*reddit*, test_stocktwits*, test_*short*, test_*float*` | 19 | routing / errors / cache / symbol map |
| Graph / wiring | `test_*analyst*, test_*execution*, test_*parallel*, test_*checkpoint*, test_*signal*, test_*router*, test_*toolnode*, test_*instrument*, test_*ticker*, test_*crypto*, test_*i18n*, test_news_lookahead` | 19 | graph edges, state, i18n, tool nodes |
| LLM / providers | `test_*provider*, test_*api_key*, test_*openai*, test_*anthropic*, test_*google*, test_*bedrock*, test_*ollama*, test_*model*, test_*reasoning*, test_*temperature*, test_*retries*, test_*minimax*, test_*deepseek*, test_capabilities` | 22 | factory, model select, key precedence |
| Scripts / screener | `test_value_screener, test_scan_*, test_sector_*, test_growth_*, test_*config_gate, test_*orderflow_evaluate, test_*stress*` | 6 | screens, scans, eval scripts |
| Smoke / misc | `test_reporting, test_pipeline, test_batch_*, test_cli_*, test_memory_log, test_news_lookahead`, etc. | rest | reports, batch, CLI flags |

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
  leak into the next (order-independent tests). Also closes moomoo contexts
  (`_close_all_ctxs`) to avoid process hang.
- `_disable_reddit_killswitch` — removes `TRADINGAGENTS_DISABLE_REDDIT` so the
  fetcher's real path runs even if a local `.env` opts out.
- `mock_llm_client` — patches `factory.create_llm_client` with a `MagicMock` for
  structured-agent tests.

## How to run

```bash
# one file
py -3.12 -m pytest tests/test_strategies_swing.py -q --no-header -p no:cacheprovider
# one test
py -3.12 -m pytest tests/test_strategies_swing.py::test_some_name -s
# a domain
py -3.12 -m pytest tests/test_strategies_*.py -q --no-header -p no:cacheprovider
# whole suite (~6 min; includes slow value_screener / LLM-mock tests)
py -3.12 -m pytest tests/ -q --no-header -p no:cacheprovider
```

Use `py -3.12` (bare `python` has no pytest).

## Test timers (required)

Every test inherits a per-test deadline so a hung vendor / network call can never
block the whole session indefinitely (``pytest-timeout``):

- **Global default: 180 s per test, thread method** — set in
  ``[tool.pytest.ini_options]`` (``timeout`` / ``timeout_method``). The thread
  method is the only one reliable on Windows (signal timers are POSIX-only).
- **Module-level override: ``pytestmark = pytest.mark.timeout(600)``** for
  modules whose tests legitimately run live vendor calls end-to-end
  (``test_value_screener``, ``test_scan_strategies``, ``test_growth_screens``,
  ``test_structured_agents``) — those measured 12-62s per test on a normal
  network, so 180s would be too tight on a slow one.
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