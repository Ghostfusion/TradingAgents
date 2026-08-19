# End-to-end how-to: screener → pipeline → reports

This walks the full daily workflow once OpenD (moomoo) is running and logged in
(one-time: install OpenD, log in with the free moomoo account, tick **remember
password**; `TRADINGAGENTS_MOOMOO_AUTOSTART=true` in `.env` handles launching it).

## 0. Environment check

```bash
py -3.12 -c "import tradingagents; print('ok')"
netstat -ano | findstr 11111      # OpenD listening
```

Config lives in `.env`. Notable on-by-default flags: `enable_events` (catalyst
overlay), `TRADINGAGENTS_MOOMOO_AUTOSTART=true`.

## 1. Cross-sectional run (B2)

Find today's candidates and analyze the top 5 in one command:

```bash
# from moomoo's daily top-losers (gated: >$10B cap, price > $15, P/E < 40)
py -3.12 pipeline.py --universe top-losers --top 5 --workers 3 --depth deep

# from a watchlist file
py -3.12 pipeline.py -f universe.txt --top 5 --date 2026-08-19

# straight tickers
py -3.12 pipeline.py AAPL MSFT NVDA --top 3
```

Output: `reports/pipeline_<ts>.md` (ranked candidates + per-symbol results)
and `reports/<SYMBOL>_<ts>/complete_report.md` per pick (with TOC), plus a
JSONL machine-readable summary.

## 2. What the catalyst overlay does (on by default)

Before each analysis the overlay fetches: next earnings date + last EPS
surprise, option-implied move / IV crush history, HIGH-importance economic
events, and FOMC probabilities, then emits a scale + verdict
(`earnings-window` / `macro-catalyst` / `fed-catalyst` /
`no-imminent-catalyst`) that de-risks position size when a catalyst is near.

Verify on a live ticker:

```bash
py -3.12 -c "
from tradingagents.strategies.catalyst import fetch_catalyst_data, build_catalyst_snapshot
from tradingagents.default_config import DEFAULT_CONFIG
d = fetch_catalyst_data('AVGO', '2026-08-19')
s = build_catalyst_snapshot(d, '2026-08-19', DEFAULT_CONFIG)
print(s['verdict'], s['scale'], s['reasons'][:2])
"
```

## 3. Single-symbol deep dive

```bash
# interactive CLI (watch agents in real time)
tradingagents

# headless, moomoo-first
py -3.12 batch.py --symbols AVGO --vendor moomoo --depth deep
```

Every report lands in `reports/<SYMBOL>_<ts>/`; open `complete_report.md` —
the TOC jumps to any team/role; the per-section files stay raw.

## 4. The new analyst tools (A-series)

Analysts can call (all moomoo, optional):

- `get_capital_flow` – weekly money-flow by order size (market analyst)
- `get_expected_move` – option-implied move at the next earnings (market)
- `get_institution_holdings` – 13F-style institutional % + change (fundamentals)
- `get_earnings_surprise_history` – EPS surprise vs estimate + reaction (fundamentals)
- `get_economic_calendar` / `get_fed_watch` / `get_market_breadth` (news)
- `get_earnings_catalyst` – implied move + IV crush history (news)

## 5. Keep the reports readable

If you changed formatting and want to re-render existing folders:

```bash
py -3.12 scripts/rebuild_complete_report.py reports/AVGO_20260819_* 
py -3.12 scripts/rebuild_complete_report.py   # all
```

## 6. Troubleshooting

- **OpenD down**: list, the router logs `Vendor 'moomoo' not configured ...`
  and falls back to yfinance; nothing aborts.
- **Catalyst scale sticky at 1.0**: log, recheck `enable_events`; a ticker with
  no calendar row (rare coverage) is neutral by design.
- **Process hangs at exit**: contexts are closed at run end & in the test
  teardown; if you still see it, ensure nothing leaves an `OpenQuoteContext`
  open at interpreter exit.

**Pro tip**: keep `.env` local — never commit it. Only source, tests, docs.