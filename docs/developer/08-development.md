# 8. Development guide

How to extend this fork safely, with the conventions a maintainer expects.

## 8.1 The working agreement (every task)

1. **Compute-as-tools** — expose deterministic calculations as `@tool`s for the
   agent LLMs (never let them re-derive or invent numbers).
2. **Keep docs true** — update README + docs + CHANGELOG on any behavior change.
   Never leave a doc stale.
3. **Commit + push** when done (Conventional Commits). If the changelog/onboard
   references a hash, commit that in a follow-up docs commit and push.
4. **No secrets** in commits — keys live in `.env` (gitignored).

## 8.2 Python env

- Always `py -3.12` (vendor venv). Bare `python` is the hermes agent venv (no
  pytest) — never use it.
- moomoo SDK + all deps are installed only in the py3.12 env.

## 8.3 Running & testing

```
py -3.12 -m pytest tests/test_X.py -q --no-header -p no:cacheprovider
py -3.12 -m pytest tests/            # full suite ~6 min (slow network tests)
py -3.12 -m ruff check tradingagents/ scripts/ tests/ cli/   # must pass
py -3.12 -m ruff format  # reformat only files you touch
```

Breakpoint debugging: add `breakpoint()` or `-s` on a test.

## 8.4 Windows gotchas (critical)

- **Heredocs mangle code** — never write file content with escapes/arrows/
  em-dashes via bash heredoc. Use the `write` tool for literal content, `edit`
  for surgical changes. Existing files are CRLF — use `\r?\n`-aware matching.
- **Two Pythons** — see §8.2.
- **OpenD leak** — never leave an `OpenQuoteContext` open at interpreter exit
  (the process hangs). Contexts close at the end of `propagate`, in test
  teardown, and via daemon-guarded atexit.
- **Port 11111** — OpenD; when down the TCP probe times out (tests mock it).

## 8.5 Adding a feature — step checklist

1. **New data source** — follow §3.3 (vendor contract).
2. **New strategy** — follow §4.6.
3. **New analyst / tool** — follow §5.2 + `graph/setup.py:setup_graph`.
4. **New provider** — `llm_clients/factory.py` + a client module +
   `api_key_env.py` if it needs a key.
5. Add config keys in `default_config.py` + `.env.example` mirror.
6. Add hermetic offline tests (mock vendor/HTTP).
7. Update README (News + feature bullet), CHANGELOG, docs.
8. Commit + push.

## 8.6 Testing conventions

- conftest autouse fixtures reset thread-local config, clear vendor cache,
  close moomoo contexts before/after each test.
- Strategy tests are pure/offline (no network).
- Slow tests exist (value_screener ~30-70s, structured_agents LLM mocks). Run
  the full suite only when needed.

## 8.7 Common pitfalls

- `No module named pytest/pandas` — you used `python`; use `py -3.12`.
- `429 from FMP/Finnhub` — vendor degrades to unavailable, falls to next
  vendor; never breaks a run.
- `NO_DATA_AVAILABLE` for options on a US name — plan lacks options permission;
  chain falls back to yfinance.
- Catalyst scale stays 1 when no imminent catalyst — by design neutral.
- NetNet always `no` on large caps — normal (CAPA - liabilities negative).
- M column `n/a` — fixed (period-order aware `{current,prior}` dicts); M now
  computes when two periods exist.

Continue to [`09-massive-integration.md`](09-massive-integration.md).