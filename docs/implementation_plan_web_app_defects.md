# TradingAgents web app (`trading_web`): defect audit & implementation plan

**Scope.** The web app is the sibling project `../trading_web` (FastAPI backend + React/Vite SPA, ~8.5k LOC:
backend 2.6k, frontend 2.2k, tests 1.3k). It is **not** inside this repository — it lives in the parent
`TradingNew` git repo, while the engine it drives is this repo (`TradingAgents`). This plan is filed under
`TradingAgents/docs/` per this project's docs convention (same place as
`implementation_plan_defect_audit.md` and `implementation_plan_calc_agent_binding.md`); move it to
`trading_web/docs/` if the app should own it.

**Audited state.**

| side | revision |
|---|---|
| engine (this repo) | `9a9e070` (working tree clean apart from the user's own untracked files) |
| web app (parent repo) | `7e2c1fc` + **one uncommitted file**: `trading_web/backend/jobs.py` (error/result slice caps 4000 → 8000) |
| live config | `trading_web/.env` sets `TRADINGAGENTS_WEB_HOST=0.0.0.0` — the app is **LAN-exposed**, and the findings below are graded against that reality |
| live artifacts read (read-only) | `data/web.db` (48 job rows), `data/audit.jsonl` |

**Method.** Three read-only audits (backend correctness/security; frontend SPA; engine-integration contract),
each required to cite `file:line` on both sides and to distinguish defects from missing features. The main
thread independently re-derived every P0 and each load-bearing P1, and read the live job store and audit log.
**No code was changed.**

**Headline.** 45 reported findings consolidate to **3 P0 + 10 P1 + 22 P2 fix units**. Two of the P0s are live
right now: one capability screen is 100% dead (engine symbol drift), and a user-submitted job has been
`running` since 2026-09-08, permanently holding 1 of only 2 job-worker slots. A third (the price chart) cannot
work in the deployed configuration because the app's own CSP blocks the chart library it loads from a CDN.

---

## 1. Severity summary

| sev | count | themes |
|---|---|---|
| **P0** | 3 | dead capability screen (engine drift) · in-process jobs with no timeout/cancel (live zombie) · CSP blocks the chart |
| **P1** | 10 | unvalidated path args reach engine writers · no 401 handling + inert logout · polling dead/never-stopping · stale error masks later results · job output discarded · preset round-trip broken · login-lockout DoS · OHLCV `open` always null · job rows leak absolute paths/tracebacks · credential saves silently revert |
| **P2** | 22 units | job-store/queue hygiene · API surface (public docs, 200-HTML fallthrough, config path leak) · audit integrity · lifecycle wiring · frontend correctness (worker cap, keystroke fetches, keys, crash-on-bad-URL, dev proxy, admin probe, submit guard) · coverage/doc claims · cross-repo contract |

Provenance: `B` = backend audit, `F` = frontend audit, `E` = engine-integration audit, `M` = verified
first-hand by the main thread. Findings marked `[INFERENCE]` were reasoned statically and are flagged as such
in place.

---

## 2. P0 findings

### W-P0-1 — The Value-Tools capability is 100% dead: the app imports a tool the engine deleted `(E, M)`

**Defect.** `capabilities.py:820-861` imports a fixed symbol list from
`tradingagents.agents.utils.analysis_tools`; line **857** still imports `get_thesis_evidence_matrix`, which was
deleted from the engine on 2026-09-11 by the approved decision in
`docs/implementation_plan_calc_agent_binding.md` §4.4 (`CHANGELOG.md` records it). The import block is wrapped in
`except Exception` → `{"ok": false, "message": "import of value tools failed: ..."}`, so **every** value-tool
call fails before dispatch. Two more references survive in the same file: `:810` (the default `selected` tool
list) and `:983` (the dispatch lambda); the SPA also advertises it (`frontend/src/App.jsx:334`).

**Verified live (this session).** `py -3.12 -m pytest tests/ -q` in `trading_web`:
**8 failed, 55 passed**, every failure reporting
`import of value tools failed: cannot import name 'get_thesis_evidence_matrix'`. A mechanical check of all 59
engine symbols the app imports found **exactly this one missing** — everything else still resolves.

**Impact.** The whole "Value tools" screen (54 tools), for every ticker, is dead in the shipped app.

**Fix.** Delete the name from the import list, the default list and the dispatch map; drop the UI option.
The engine-side deletion stands — the app must stop importing a symbol that no longer exists.

**Gate.** (a) The 8 failing tests must pass. (b) New contract test in the web repo: for **every** name in the
default tool list and the dispatch map, assert `hasattr(engine_module, name)` — this is the gate that would have
caught the drift, and it must be able to fail (run it against a deliberately wrong name in the test).

---

### W-P0-2 — In-process jobs have no timeout and no cancel path; a worker slot is already lost `(B, M)`

**Defect.** The job pool is `ThreadPoolExecutor(max_workers=config.MAX_WORKERS)` = **2** (`jobs.py:14`,
`config.py:80`). Subprocess capabilities get a 900/2400 s timeout (`capabilities.py:121`), but `run_batch` and
`run_value_tools` run **in-process** in the worker (`capabilities.py:224-308`) with nothing bounding them, and
there is **no cancel route** anywhere in `main.py`.

**Verified live (this session).** Read-only query of `trading_web/data/web.db`:

```
run_batch | running | created 2026-09-08 21:50 | age 62.7 h | error NULL | result NULL
status histogram: done 17 | failed 30 | running 1
```

A real user-submitted batch has been `running` for ~2.6 days, silently holding half the pool. Its siblings show
that boot-time recovery does work (`server restarted while job in flight` rows exist), so this is a hung worker,
not a stale row. The only remedy today is a server restart.

**Impact.** Permanent 50% throughput loss on a 2-slot pool; a phantom "running" row in the timeline forever;
`recover_stale_jobs` cannot help because the server has stayed up.

**Fix.** (a) Per-job wall clock (`config.JOB_TIMEOUT_SECONDS`) enforced by a watchdog that marks the row
`failed`/`timed out` and kills the process tree — the worker thread itself cannot be interrupted. (b)
`POST /api/jobs/{job_id}/cancel` (owner + CSRF) that sets `cancelled`, sets a cancel flag and kills any tracked
child subtree. (c) A reaper that fails `running` rows older than the timeout at boot **and** periodically, so a
hung worker cannot hide.

**Gate.** Register a capability that blocks on an `Event`: assert (i) after the timeout the row is
`failed`/`timed out` and the executor's active count returns to 0, and (ii) `cancel` on a running job returns
200 and the row becomes `cancelled`.

---

### W-P0-3 — The price chart is blocked by the app's own CSP `(F, M)`

**Defect.** `TickerChart.jsx:17-18` loads Plotly from `https://cdn.plot.ly/...` by injecting a `<script>`, while
`security_headers()` sets `script-src 'self'` (`security.py:177-187`) and the middleware applies those headers to
**every** response — including the `FileResponse` of `frontend/dist/index.html` served by the SPA catch-all
(`main.py:47-52`, `:553-561`). The browser therefore refuses to load the library.

**Verified live (this session).** Header source and injection site read directly; `frontend/dist/assets/*.js`
contains the CDN URL (so the shipped bundle is affected, not just `src`).

**Impact.** "Show chart" is a documented feature (`HelpGuide.jsx:196`) that cannot work in the deployed app. It
works under `npm run dev` (Vite serves the document without the backend's CSP), which is how it escaped notice —
and the surfaced error blames the CDN, not the policy.

**Fix.** Ship the library: `npm i plotly.js-dist-min` and lazy-`import()` it (keeps the code-split), or place
`plotly.min.js` in `frontend/public/` and load `/plotly.min.js`. **Do not** loosen `script-src` to a CDN. Also
cache only the *fulfilled* promise so a transient failure is retryable.

**Gate.** Playwright against the real backend (`py -3.12 -m backend.main`, which sets the CSP): log in → Reports →
type a symbol → Show chart → assert the Plotly container appears and no `securitypolicyviolation` fired. Fails
today.

---

## 3. P1 findings

### W-P1-1 — Unvalidated path/kwarg arguments reach engine writers (escapes the project) `(E, B, M)`

`JobIn.args` is a free-form dict (`main.py:109-111`) spread into the capability (`jobs.py:50-58`), and these
values go verbatim into argv as **writes** or reads: `--out-dir` (`capabilities.py:427-428`, `:564-565`, `:609-610`), `--journal`
(append, `:431-432`), `rebuild_complete_report` positional dirs (`:761`), `--results-dir`/`--report-dir`/`--audit-path`/
`--ledger-path`/`--data-dir` (`:470-472`, `:1046`, `main.py:364`). The engine resolves them with `resolve_output_path`,
which returns **absolute paths unchanged**. The free-form `limits` dict (`capabilities.py:470-472`) additionally
turns any key into `--{key} value` (flag injection: `{"limits": {"out-dir": "C:/tmp"}}`), and `nightly`/`premarket`
expose `skip_llm=False` even though the README says the web pins `--skip-llm`.

**Impact.** Any authenticated account (and any saved preset) can make the engine write or append outside the
project and read arbitrary directories — directly contradicting the README's "path defense … no file can escape",
which is only true of the *reader*. On the live LAN-exposed deployment that is a remote write primitive.

**Fix.** Validate every path-ish argument before argv (`security.safe_relpath`/`resolve_under` against an
allowlisted root per capability; reject absolute, `~` and drive-qualified), promote `limits` to the nine known
screener gates, drop `journal`, force `--skip-llm`, and clamp `days`/`max_days`. Validate `args` against the
capability signature so unknown kwargs 400 instead of reaching the engine.

**Gate.** For each write-taking capability, `out_dir="C:/tmp"`, `journal="/etc/x"`,
`report_dirs=["C:/tmp"]` return `ok:false` **and never spawn a subprocess** (capture the argv as the existing
tests do); `limits={"out-dir": ...}` is rejected.

### W-P1-2 — No 401 handling; an expired session looks like an empty account, and Logout is inert `(F)`

`api.js:20-24` discards the HTTP status; `App.jsx:1256-1269` sets `user` once and never invalidates it; five page
loads swallow errors (`App.jsx:90-103, 263, 1111, 1135-1140`) so an expired session renders "no reports yet" with
the sidebar still saying "Logged in as …". `logout()` rethrows (`api.js:45-51`) — with an expired session the CSRF
fetch 401s and the POST 403s, so `doLogout` (`App.jsx:1272`) never clears `user`: **the button does nothing**.

**Fix.** Attach `err.status`; add one global 401 hook in `api.js` (`setAuthErrorHandler`) wired to
`setUser(null)`; make `logout()` best-effort (`catch {}` + `finally`); replace swallow-only catches with a visible
error state (never render a failed load as an empty one).

**Gate.** Stub `/api/me` 200 → `/api/reports` 401: assert the login form renders and "no reports yet" never
appears. Stub a failing logout: assert the login form still appears.

### W-P1-3 — Polling is dead or never stops `(F)`

`usePoll` returns a tick that **12 of 13 call sites discard** (`App.jsx:31-37` and the sites listed in the frontend
audit), so Dashboard, Reports, Signals and Audit never refresh — while the pages that do discard it re-render every
2.5 s forever (a ~44-row Value-Tools form re-rendering on a timer). `JobsTimeline`/`Watchlist`/`JobsList` keep
polling after every row is terminal, and no poll guards against an older response overwriting a newer one.

**Fix.** Replace the hook with `usePolledFetch(path, ms)` that owns the timer **and** the fetch, consume it on the
four data pages, delete the dead calls, stop when nothing is `queued`/`running`, and sequence-guard or abort
in-flight requests.

**Gate.** Fake timers: mount Audit, advance 15 s → two fetches; with all jobs `done`, advance 30 s → one fetch; a
late older response must not overwrite fresh data.

### W-P1-4 — One failure permanently hides every later result `(F)`

`ResultBox` returns the error branch before the result branch (`App.jsx:40-41`), and `Raw`/`Nightly`
(`App.jsx:1078-1085`, `918-930`) never reset `error`/`result` on submit (nine sibling pages do). Same class in
`Watchlist.jsx:18-25`, `JobsTimeline.jsx:17-24`, `ApiKeys.jsx:25-31`, `PresetBar.jsx:17-24`, `App.jsx:1135-1140`:
a successful `load()` never clears a previous error banner. `ResultBox` also ignores `ok:false` envelopes, so a
failed capability renders as ordinary output.

**Fix.** Reset both on every submit, clear the error on every success path, and render `ok === false` with the
error style.

**Gate.** RTL: failing run then successful run on `Raw` → the success text is present and the error is gone;
Watchlist 500 → 200 on the next tick removes the banner.

### W-P1-5 — Successful async job output is discarded `(E, M)`

`jobs.py:42-47` persists only `status`/`error`/`result_path`, and `db.set_job`'s allowlist (`db.py:138-141`) has no
column for a capability's output; only `run_batch` returns `results`. So `action_report`, `strategy_quality`,
`capital_income`, `config_gate`, `risk_report`, `orderflow_eval`, `screener`, `pipeline`, `premarket`, `nightly`,
`backtest`, `rebuild_report` all finish `done` with **no visible output** — indistinguishable from an empty run.

**Verified live (this session).** The live store has 20+ `done` rows with `result_path` NULL, including
`run_value_tools`, `run_strategy_quality`, `run_screener`, `run_backtest`.

**Fix.** Add a `message`/`output` column (allow-listed in `set_job`, redacted, exposed by `GET /api/jobs/{id}`),
persist `result.get("message")` on success, return a parsed structured payload for `--json` capabilities, and
never truncate JSON mid-token (truncate by elements; add `result_truncated`). `[F-05]`

**Gate.** Monkeypatch a capability to return `{"ok": True, "message": "ACTION REPORT: ..."}`; assert the job row
exposes it; plus an >8 kB stdout case that is either fully preserved or explicitly flagged truncated.

### W-P1-6 — Screener presets do not round-trip, and two advertised controls do not exist `(F)`

`applyScreenerPreset` (`App.jsx:465-479`) restores ~8 of ~22 saved fields — `scan`, `date`, `rank`, the six gates,
`intraday`, `enable_float`, `alloc`, `value_dip_loose` are dropped — yet the UI reports "loaded preset". Separately,
`--alloc` has no input control anywhere and `market` is hardcoded `"US"` (`App.jsx:435, 458, 461`) while the help
text and README advertise both. (`RunBatch.onApply` restores everything; the Screener is the outlier.)

**Fix.** Derive one `SCREENER_FIELDS` list used by both `screenerArgs()` and the apply path; add the Allocation
checkbox and the market selector (or delete the claim). `[F-15]`

**Gate.** RTL: set Scan=value-dip + gates + `--alloc`, save, change the form, apply → `screenerArgs()` equals the
saved args.

### W-P1-7 — Login lockout is a one-account DoS and an unbounded map `(B, M)`

`security.py:191-217` keys the counter on the **client-supplied username only** (the comment claims "+ IP"; no
request reaches it), in memory. The live `users` table has exactly one account (`admin`). So 5 anonymous wrong
passwords lock the only admin out for 5 minutes, repeatable forever; the counter resets on restart and is per
worker; and each failed login permanently retains `{username: [...]}` — with no length bound on `username`
(`main.py:104-109`), a large body is a large permanent key.

**Fix.** Add the per-IP dimension; cap/evict the map; validate `username` (`max_length=64`) and `password`
(`max_length=1024`); either persist counters or document the per-process semantics.

**Gate.** (i) Failures for user A also block user B from the same IP; (ii) 1 000 distinct long usernames leave
`len(_failed) <= cap`; (iii) a 10 MB username → 422.

### W-P1-8 — Every OHLCV bar loses its `open`; the documented `absence` envelope is never emitted `(E)`

`capabilities.py:1111-1120` reads `ohlcv.get("opens")`, but `scripts/value_screener.py:420-475` (`_fetch_ohlcv`)
returns `closes/highs/lows/volumes` only on the default vendor path, so `open` is `null` for every bar →
`TickerChart.jsx:74` feeds nulls to Plotly. The same seam never returns the `absence` envelope the README
documents (`README.md:13-18`), so the "no data vs rate-limited" distinction does not exist. `[V5]`

**Fix.** Make the engine seam return one shape (`opens` included) and surface the typed vendor failure; or, if the
app must stay engine-shape-agnostic, label the unavailable field explicitly instead of emitting `null`.

**Gate.** Stub the documented vendor shape and assert `rows[0]["open"] is not None`; stub the typed failure and
assert `absence.reason`; correct or delete the README claim.

### W-P1-9 — Job rows leak absolute server paths and raw tracebacks `(B, M)`

`_redact_job` (`main.py:234-257`) masks `result_path` lexically: a JSON blob (which is what `run_batch` stores)
starts with `[`, so neither the repo-prefix test nor `isabs` matches and the absolute path passes through — live
rows return `"report_dir": "D:\\Users\\vince\\...\\trading_web\\reports\\..."`. `error` is copied verbatim and
contains subprocess tracebacks with absolute paths. The docstring's "never leak the server's filesystem layout"
is therefore false, and the existing test only asserts on a path-*shaped* value.

**Fix.** Mask structurally (parse JSON → mask every string → re-serialise), run `security.redact()` plus repo/home
prefix masking over `error`, and prefer storing report paths relative to `REPORTS_DIR`.

**Gate.** Persist a job whose `error` embeds the repo path and whose `result_path` is a JSON blob with an
out-of-repo absolute path; assert the API response contains no `X:\` string and no repo prefix.

### W-P1-10 — Credential saves silently revert after restart `(B)`

`credentials.py:103` writes to `trading_web/.env`, but `config.py:37-38` loads `TradingAgents/.env` **first** with
`override=False`, and 6 of the 7 managed keys are defined there. So a rotated key takes effect in-process
(`os.environ[key] = value`) and silently reverts on restart, while the UI keeps showing the old masked value.
Also, the value is not newline-validated, so a value containing `\n` injects extra `KEY=value` lines into the file.

**Fix.** Write to the file that currently defines the key (or make the web `.env` authoritative with
`override=True`), return the effective source per key, and reject values containing newlines/`=`.

**Gate.** Point `TRADINGAGENTS_REPO` at a tmp dir whose `.env` defines a key; save a new value; reload config from
disk in a clean env; assert the new value wins. Assert a newline-containing value → 400.

---

## 4. P2 fix units

| unit | covers | fix (summary) |
|---|---|---|
| W-P2-1 job-store hygiene `(B)` | F-06, F-15 | guard the **finishing** `set_job` (a DB error currently leaves `running` forever, unlike the guarded failure path), `PRAGMA journal_mode=WAL` + `busy_timeout`, `PRAGMA user_version` + ordered migrations, `CREATE INDEX jobs(username, created_at DESC)`, close connections |
| W-P2-2 queue hygiene `(B)` | F-07 | reject duplicate `(user, capability, args)` while queued/running (409), per-user pending cap, gate `rerun` on `done`/`failed` (its docstring already promises it), expose queue depth |
| W-P2-3 concurrency composition `(E)` | V11 | 2 jobs × 4 batch workers = 8 in-process graph workers vs the engine's 4-worker rationale (`batch.py:30-48`, moomoo connection limit): one global semaphore across in-process batch workers. `[INFERENCE]` — gateway behaviour not reproduced |
| W-P2-4 API surface `(B, E, F)` | F-08, F-09, V9, F13 | JSON 404 for unknown `/api/*` (today the SPA catch-all answers HTML **200**), put `/api/docs` + `/api/openapi.json` behind auth or disable them (currently **public** on a `0.0.0.0` bind), implement or delete `GET /api/summaries/{name}` + `read_batch_summary` + the no-op `PUT /api/config`, correct the module docstring's route list |
| W-P2-5 `/api/config` exposure `(B)` | F-11 | invert the denylist to an allowlist: absolute paths (`project_dir`, `results_dir`, `data_cache_dir`, `memory_log_path`) and `moomoo_account` are currently returned to any authenticated caller |
| W-P2-6 audit integrity `(B)` | F-10 | log the real user on logout (currently the literal `"?"`), add rotation/retention + tail reads (the whole file is parsed per request), and make the test suite write to a temp `AUDIT_PATH` (it currently appends to the **real** `data/audit.jsonl` — proven from the live log) |
| W-P2-7 CSRF store bound `(B, F)` | F-12 | prune expired entries on mint and cap the dict; nothing is cleared on logout (currently only presented tokens are pruned) |
| W-P2-8 app lifecycle `(B)` | F-13 | move `init_db`/`ensure_admin`/`recover_stale_jobs` into an ASGI **lifespan** (today `uvicorn backend.main:app` runs with no DB/admin), call `jobs.shutdown()` (currently dead code) and kill tracked child PIDs on exit, and stop `contextlib.suppress`-ing recovery failures |
| W-P2-9 path-guard residual `(M)` | — | `security.resolve_under` checks `base in child.parents` on the **unresolved** child, so a symlink/junction *inside* `reports/` escapes lexically; resolve before the check. (Read-only audit could not create a junction to prove it end to end.) |
| W-P2-10 frontend worker cap `(F)` | F9 | the SPA hardcodes `maxWorkers = 4` while the backend reads `TRADINGAGENTS_MAX_WORKERS`: expose the cap and use it for the pre-check and the input's `max` |
| W-P2-11 chart & table identity `(F)` | F10, F11, timer #15 | one OHLCV request per keystroke after "Show chart" (split committed symbol from the input); array-index React keys on sortable/reversed lists; `ReportView` has no cancel guard, so navigating A→B can render A's data |
| W-P2-12 crash containment `(F)` | F12, F18 | `decodeURIComponent(window.location.pathname)` on `/reports/%` throws and the boundary **outside** the router replaces the whole app (Reload loops): use `useParams`, move the boundary inside the router, add a 404 route |
| W-P2-13 dev proxy `(F)` | F14 | `vite.config.js` hardcodes `127.0.0.1:8000` while host/port are env-driven → `npm run dev` breaks silently when the port changes |
| W-P2-14 admin probe `(F)` | F16 | the keys page probes the admin role by downloading the **entire audit log** and starts `admin=true` so buttons flash; expose the role on `/api/me` |
| W-P2-15 submit guard `(F)` | F17 | no submit button is disabled in flight → a double-click queues two LLM batches |
| W-P2-16 frontend hygiene `(F)` | F18 | impossible dates accepted (`2026-13-45`), `login()` makes a guaranteed-401 `/api/csrf` call before `/api/login`, dead `export { csrfToken }`, unused `compact`/`user` props, `path="*"` silently renders Dashboard |
| W-P2-17 coverage claims `(E)` | V7, V8, F15 | rewrite "**every** capability" / "every repo entry point" / "44 computed tools" (the default list is 54 names, and 17 `scripts/` entry points have no surface); reconcile the counts |
| W-P2-18 batch parity `(E)` | V12 | the CLI batch's same-night pre-market re-check lives in `batch.main()`, not `batch.analyze()` which the web calls; `--force-run`/`--regions` (nightly) and several `backtest`/`risk_report` flags are not forwarded |
| W-P2-19 provenance/claims in comments `(B, M)` | — | `security.py:191` "per username + IP" (no IP), `main.py:187-188` "token in header + body-cookie roundtrip" (header + server store only), `jobs.py` comment claiming child processes die with the server, `conftest` "never touch the real …" (audit path is not isolated) |

---

## 5. Verified clean — do not "fix" these

Confirmed by reading both sides (`M` = re-verified by the main thread):

- **No XSS.** No `dangerouslySetInnerHTML`/`innerHTML`/`eval`; every server string renders as a React text node;
  one static `href`, no `target=_blank`.
- **SQL.** Every statement is parameterised, and `set_job`'s column names are allow-listed, so no injection or
  arbitrary-column write.
- **Passwords/sessions.** `hashlib.scrypt` (n=2¹⁴), stored hashes only, constant-time compares
  (`hmac.compare_digest`); HTTP-only/SameSite=lax cookie, 8 h TTL. Residual: stateless tokens mean logout cannot
  revoke a stolen cookie (not claimed otherwise).
- **CSRF coverage.** 11/12 mutating routes call `require_csrf`; the SPA attaches a fresh single-use token per
  mutation and the audit could not construct a token race; login is exempt but the CORS policy + SameSite cover it.
- **Raw commands.** Exact full-string allowlist membership *before* `split()`, argv list, no shell, fixed cwd,
  timeout — not extensible by input.
- **Report reads.** `safe_relpath` + `resolve_under` reject `..`, absolute and drive-qualified names before any
  open (only the symlink residual of W-P2-9 and the write side of W-P1-1 remain).
- **No shell anywhere.** Every subprocess call passes a list to `Popen`; symbols/paths cannot escape into a shell.
- **Secrets.** `data/`, `.env` are git-ignored and untracked (verified against the parent repo).
- **Engine contract, everything else.** All 59 imported engine symbols except W-P0-1 exist at HEAD; all 19
  raw-allowlist entry points exist; every forwarded CLI flag exists in the target parser; `sys.path`/cwd/`.env`
  precedence behave as designed; `TRADINGAGENTS_MAX_WORKERS` semantics match; `verify_flags.json` matches the
  engine's `--verify` step; the live analyst wire key `social` is still correct.
- **Timer hygiene.** Every `setInterval` is cleared on unmount (the defects are *what* is polled and *how long*).
- **Job status vocabulary, watchlist normalization, `SignalTable` formatting, bundle secrets** — checked, clean.

---

## 6. Work plan

Ordering rule as in this project's other plans: **gate ships with its fix**, no phase starts before its
predecessor's gate is green, and a gate must be shown failing before it is trusted. The app has **no frontend test
infrastructure today** (`package.json` has no test script or vitest/RTL dependency), so X6 must begin by adding the
harness — that is a prerequisite, not a nicety.

| phase | content | gate |
|---|---|---|
| **X1** unbreak + contract `(W-P0-1)` | drop the deleted symbol from the import/default/dispatch/UI; add the engine-symbol contract test | the 8 failing tests pass; the contract test fails on a deliberately wrong name |
| **X2** job lifecycle `(W-P0-2, W-P2-1, W-P2-2)` | job timeout + watchdog, cancel route, reaper (boot + periodic); WAL/busy_timeout; guarded finish write; dedupe + pending cap + `rerun` status gate | blocking-capability timeout test; cancel test; two concurrent `run_batch` calls respect one global cap; DB-error-on-finish test |
| **X3** ship the chart library `(W-P0-3)` | local Plotly (npm dep or `public/`), fulfilled-promise cache only | Playwright on the CSP-bearing backend shows the chart and no CSP violation |
| **X4** argument validation `(W-P1-1, W-P2-9)` | path/kwarg validation per capability; typed `limits`; no `journal`; forced `--skip-llm`; clamp ints; resolve-before-check path guard | every write-capability test rejects absolute/traversal args **without spawning**; unknown kwarg → 400 |
| **X5** result & leak correctness `(W-P1-5, W-P1-8, W-P1-9, W-P2-4, W-P2-5, W-P2-6, W-P2-7, W-P2-8)` | persist job output + structured payloads; engine OHLCV `opens`/`absence`; structural masking; JSON 404 + docs behind auth; config allowlist; audit integrity (+ test isolation); CSRF cap; lifespan/shutdown | per-item tests as listed in §3–§4; each gate demonstrated failing first |
| **X6** frontend correctness `(W-P1-2, W-P1-3, W-P1-4, W-P1-6, W-P2-10 … W-P2-16)` | **first add vitest + RTL + fake timers (and Playwright for the CSP/URL cases)**; then 401 hook + best-effort logout; `usePolledFetch`; error-state reset; preset round-trip + missing controls; worker cap from the API; keystroke/keys/cancel-guard; crash containment; dev proxy; admin role; submit guard; hygiene | RTL/Playwright tests as specified per finding; the harness must be able to fail (assert one deliberately broken case) |
| **X7** docs & claims `(W-P2-17, W-P2-18, W-P2-19, W-P0-1 doc note)` | rewrite the coverage claims and the API notes; fix the code comments that assert defences they do not implement; record this audit's outcome in the app README | a doc-claim test in the app repo mirroring the engine's `tests/test_doc_binding_claims.py`: every claimed route exists, every claimed tool name is importable, every claimed raw entry point is in the allowlist |
| **X8** cross-repo contract (below) | the registry + the process rule | see §7 |

---

## 7. Cross-repo contract: why this drifted, and what would stop it

This audit's P0-1 is **not** an app bug at heart: the engine deleted a tool (correctly, by an approved decision)
and the sibling app found out when a human ran its test suite. Nothing in either repo would have caught it earlier.

1. **The referenced contract document does not exist.** `docs/design_fincept_terminal_integration.md:92` calls
   `docs/web_TOPICS.md` in `trading_web` "the canonical registry table (the … REST seam)" — that file is absent
   from both repos, so the surface the engine promises the app has never been written down.
2. **The engine's own convention is manual.** `CHANGELOG.md` entries say "no trading_web change (LLM-facing
   tool)" — a human judgement, unenforced. The W5 deletion that broke the app did not carry such a note.
3. **No CI in either repo** (`.github/workflows` absent on both sides), so the app's own suite — which *did*
   detect the break, 8 failures — is only run when someone remembers.
4. **The app duplicates the engine's "what is callable" decision** (`capabilities.py` imports a symbol list and a
   54-name dispatch map) instead of resolving through the engine's single source (`agents/toolsets.py`,
   `agent_utils` re-exports), so any engine tool change is a potential app outage and one bad name kills all 54.

**Plan for X8.** (a) Write `trading_web/docs/web_TOPICS.md` as the registry: engine symbol/entry point → web
capability → owning file, generated where possible and checked by X7's doc-claim test. (b) Have the app resolve
tools from the engine's public surface (a name registry) and fail **per tool** rather than per import block, so one
deletion degrades one entry. (c) Add the missing engine-side rule: any engine change that removes or renames a
symbol/flag/format the web consumes must state the web impact in its CHANGELOG entry (this plan's X7 adds the
app-side test that makes the claim checkable). (d) Optional but cheap: a weekly/at-commit CI job in the parent
repo running `pytest trading_web/tests -q` plus the engine's own suite.

---

## 8. Deliberate non-goals

- **No change to the engine's binding decisions.** Reconciling `get_thesis_evidence_matrix` means deleting the
  app's reference, not restoring the tool.
- **No execution/trading surfaces.** The app stays analysis-only.
- **No re-architecture of the app** (no async job runner, no websockets, no auth provider). The findings are
  fixable within the current shape; X8(b) is the only structural change proposed, and it is scoped to tool
  resolution.
- **No loosening of the CSP** to make the chart work.

## 9. Decisions the owner should make

1. **Job timeout value and semantics** — a batch can legitimately run for hours. Proposed: `JOB_TIMEOUT_SECONDS`
   default 3600 for `run_batch`, 900 for the rest, configurable by env; cancel is the escape hatch for long runs.
2. **Credential precedence** — make `trading_web/.env` authoritative (`override=True`) as the primary fix, or keep
   the engine's precedence and write to the defining file. The first is simpler; the second preserves "engine .env
   wins" as a documented principle.
3. **`/api/docs` + `/api/openapi.json`** — disable, or require auth. (They are public today on a `0.0.0.0` bind.)
4. **Missing Screener controls** (`--alloc`, market) — add the inputs, or delete the help/README claims.
5. **Frontend test harness choice** — vitest + RTL (+ Playwright for the CSP and URL cases) is assumed; if another
   harness is preferred, X6's gates change shape.

## 10. What this audit could not verify

- **No runtime execution beyond the app's test suite**: `[INFERENCE]` marks the moomoo gateway limit interaction
  (W-P2-3), the Swagger-CDN detail behind W-P2-4, and the SQLITE_BUSY trigger behind W-P2-1.
- **File ACLs / modes** of `data/web_secret.key` and `data/web.db` (written with default umask, no `chmod`).
- **The symlink/junction escape** in `resolve_under` (needs a write to create the junction).
- **`frontend/dist/` freshness vs `src/`** — the bundle contains recent markers (`knife-z`, the CSV/Plotly URL),
  but a hash comparison needs a build; a "dist is stale" CI check is worth adding.
- **Which specific capability hung the live job** (needs the running process).

## 11. Status

| phase | state | notes |
|---|---|---|
| X1 … X8 | **not started** | no code changed by this audit |

*Filed 2026-09-11. Sources: three read-only audits (backend / frontend / engine-integration) with `file:line`
evidence on both sides, plus main-thread verification of every P0 and the live job store, audit log and engine
symbol surface.*
