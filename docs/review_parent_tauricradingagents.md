# Review: upstream `TauricResearch/TradingAgents` vs our fork

Date: 2026-09-08 · Scope: read-only review, NO merge, no code changes.
Upstream HEAD: `be952b8` (post-0.4.0). Our fork: `Ghostfusion/TradingAgents` (branch
`main`, ~100+ local commits beyond upstream).

## Verdict

Our fork contains the ENTIRE upstream tree (same file layout — cli/, tests/,
dataflows/, .github/ci, Docker, pyproject) **plus** a large body of own work.
Upstream has released nothing in the last ~2 months that we lack: the 0.4.0
(2026-08-31) items are the very correctness fixes we already carry (look-ahead
FRED/news/social, memory point-in-time, latest-bar handling, debate-opening,
checkpoint, trader price grounding). Every upstream file/dir spot-checked
exists in our tree (`cli/main.py`, `tests/test_fred.py`,
`tests/test_polymarket.py`, `.github/workflows/ci.yml`, `docker-compose.yml`,
`pyproject.toml`, `scripts/smoke_structured_output.py` — all HAVE).

## Genuinely-new-in-upstream candidates (worth a peek, not actionable)

- **0.4.0 "silent Hold → REVIEW sentinel"** (`parse_rating` change): a fullwidth
  colon in a PM rating previously coerced to tradeable Hold; upstream now
  surfaces `REVIEW`. Our `parse_rating` in `tradingagents/agents/utils/rating.py`
  keeps a silent default for compat callers — the exact class we've seen bite
  (the "cap-forced final report turn returned empty" family), so this one is a
  real candidate to adopt (low risk, isolated).
- **0.4.0 "Premature reflection wait for full holding window"** (#1169) + "Memory
  point-in-time guard" (#1251): upstream resolves a decided position only after
  its holding window fully trades, and a historical run only sees lessons whose
  outcome date is known by the trade date. We have a memory log; a PIT/resolution
  window guard would strengthen backtest fidelity. Medium effort, isolated.
- **DeepSeek via OpenRouter namespace strip** (#1199): upstream strips the
  `deepseek/` prefix so the native DeepSeek capability quirks (no object-form
  `tool_choice`) apply, instead of defaulting to the OpenAI-compatible path. We
  route `deepseek/deepseek-v4-flash-0731` through OpenRouter today; if we ever
  hit a tool_choice rejection, this is the fix pattern.
- **0.4.0 models** (GPT-5.6 / GLM-5.3): irrelevant — we pin our own models
  (tencent/hy4-preview deep, deepseek-v4-flash quick + backup gpt-5.6-luna).

## Things upstream has that we explicitly DIVERGE from (not gaps)

- Upstream uses hardcoded finite sets (4 analysts, no external data vendors
  beyond AV/yfinance/FRED/Polymarket, no moomoo/eodhd/tiingo/fmp/etc., no
  `--vendor` presets). Our fork: 44 computed tools, forced-tool evidence
  gatherer, report verifier, structured debates/judge, risk governor,
  value/sector/pipeline/screener engines, moomoo data layer, EODHD loader,
  trading_web app. These are the value the fork adds on top of upstream.

## Recommendation

No merge, no sync. Adopt at most item 1 (REVIEW sentinel) when convenient —
it's a 5-line, high-value hardening already proven upstream. Items 2 and 3 can
sit as future work; item 4 is N/A. Everything else upstream has, we have a
superior version of.