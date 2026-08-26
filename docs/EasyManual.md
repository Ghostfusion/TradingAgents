# EasyManual — TradingAgents for humans (teenager edition)

Hey! 👋 This repo is a **team of robot analysts** who look at stocks and tell
you what they think — Buy, Hold, Sell, and how much. Think of it like a
fantasy team, but instead of points you get a **written report card** for any
company.

This manual explains how to use it without a finance degree. The big serious
manual is `docs/howto_end_to_end.md` — read this one first if you're new.

---

## 0. The ONE rule you must remember

On this computer there are **two Pythons**. One is a decoy 🪤:

| Command | Which Python | Can it run this project? |
| --- | --- | --- |
| `python` | a random agent venv | ❌ NO (no pytest, no pandas) |
| `py -3.12` | the real one | ✅ YES, always |

**Rule: type `py -3.12` every single time.** Every command in this file uses
it. If you get `No module named pytest`, you used the wrong one.

---

## 1. What is this whole thing?

A company is like a player. You want to know: *should I buy their jersey?*

This project gets a **team of 4 analysts** to look at the player:

1. 🎯 **Market Analyst** — the charts (price up/down, is it super volatile?)
2. 💬 **Sentiment Analyst** — the gossip (news, Reddit, Twitter vibes)
3. 📰 **News Analyst** — the headlines (world events, earnings drama)
4. 📊 **Fundamentals Analyst** — the report card (sales, profit, debt)

Then they **debate** (Bull = "buy!", Bear = "nah!"), a **Research Manager**
writes the plan, a **Trader** says where to enter/exit, three **risk analysts**
argue, and the **Portfolio Manager** makes the FINAL call and assigns a grade:

```
Buy 🟢  |  Overweight 🟢  |  Hold 🟡  |  Underweight 🟠  |  Sell 🔴
```

After that, some **robots that do math** (no vibes allowed) double-check the
size and blast a giant STOP LOSS warning if something smells risky.

---

## 2. The easiest way to use it: the web app 🖥️

There's a fancy website now. Start it:

```bash
cd /d/Users/vince/PycharmProjects/TradingNew/trading_web
py -3.12 -m backend.main
```

Open **http://127.0.0.1:8000** in your browser. Log in with the admin
username/password from `trading_web/.env` (or `data/admin_credentials.txt` if
you never set one).

Then you can click:
- **Run batch** → type some tickers (like `AAPL NVDA`) and hit go
- **Screener** → find cheap good companies (the "value" mode)
- **Reports** → read the report cards
- **Audit** → who did what

Buttons queue up real work — watch the **Jobs** table go from
`queued → running → done`.

---

## 3. The other ways to run it (terminal aliens are fine too)

### Run one or many companies

```bash
py -3.12 batch.py --symbols AAPL MSFT
py -3.12 batch.py --symbols NVDA MSFT AAPL 0700.HK BTC-USD --date 2026-08-19
```

`--date` is the "pretend it's this day" knob. `--depth deep` = argue a lot.

### Find GOOD companies automatically (pipeline)

```bash
py -3.12 pipeline.py --universe top-losers --top 5
```

It screens a bunch, ranks them, and runs the full team on the best few.

### The "buy cheap stuff" lab (value screener)

```bash
py -3.12 scripts/value_screener.py AAPL MSFT GOOG
py -3.12 scripts/value_screener.py --scan value-dip --alloc
```

Screens like Magic Formula, and fun scans like `swing` / `vcp` / `value-dip`.

### The "should I act now?" report (action report)

```bash
py -3.12 scripts/action_report.py
```

Checks the newest report for each basket holding (Underweight/Sell = trim) and
for each non-basket candidate (Overweight/Buy = add), then checks the report's
stated condition (e.g. "re-enter at $147.60") against the live price — it tells
you ADD / TRIM / MONITOR.

---

## 4. How to read the report card 📄

Every run makes a folder under `reports/`, like
`reports/AAPL_20260819_181500/`:

```
1_analysts/        → what each analyst saw
2_research/        → the Bull vs Bear debate + the plan
3_trading/         → where to enter, where to stop
4_risk/            → the risk team arguing
5_portfolio/       → THE final decision (read this!)
complete_report.md → everything in one file
```

**The last page is the boss.** It has a grade (Buy/Hold/...), how big the
position should be (like 5% of your account), and a stop loss (the "we bail
below this price" level). There's also a `Risk Gate` section — if it says
**REJECT**, the robots said "absolutely not."

---

## 5. Robot math that guards the decision 🧮

After the humans-of-AI talk, pure math runs (no opinions allowed):

- **Catalyst**: is an earnings report or Fed meeting coming soon? → shrink size
- **Risk governor**: too much risk? → PASS / WARN / REJECT
- **Tranche plan**: buy in 3 chunks (30/30/40) instead of all at once
- **Pre-market review**: check the report again the next morning before market
  opens (CONFIRM / REVISE / REJECT)

You don't have to understand the formulas — just know the robots won't let
greed decide.

---

## 6. The magic environment thing (.env)

Secret keys live in a file called `.env` (it's invisible to git, on purpose).
To make the app read your login from it:

```bash
cd /d/Users/vince/PycharmProjects/TradingNew/trading_web
py -3.12 -m backend.main   # starts the site
```

That's it — the app auto-reads `.env`. Put the admin user/pass there and
you're done (see `.env.example`).

---

## 7. Tests, timers, and being responsible ⏰

- Every test has a **timer** so nothing hangs forever (180s each, 30 min cap).
  Don't remove timers — they're the seatbelts.
- Everything is **analysis only**. No real money moves, no real orders. Treat
  it like a very smart Wikipedia for stocks, not a money machine.
- If a number is missing, the robots write "unavailable" — they **never make
  up** numbers. Don't you either.

---

## 8. Oops, I broke it (troubleshooting for beginners)

| Problem | Fix |
| --- | --- |
| `No module named pytest/pandas` | You used `python`. Use **`py -3.12`**. |
| "no prior report found" | You ran the pre-market review without a report first. Run a batch, then review. |
| Site won't start, port 8000 busy | `set TRADAGENTS_WEB_PORT=8001` (CMD) and restart. |
| catalyst scale stays 1 | No event coming soon — that's normal (not a bug). |
| M column says `n/a` | Statements missing a year-ago period. Normal for some stocks. |
| Everything slow | The next-day checks fetch real data. Give it a minute — timer will save you anyway. |
| Forgot the admin password | Delete `trading_web/data/web.db` and restart — it makes a fresh admin. |

---

## 9. Words you'll hear (mini glossary) 🧠

- **Ticker** — the short code for a company (AAPL = Apple).
- **ATR** — a robot measure of "how jumpy is this stock". Bigger = wilder.
- **RSI** — a 0-100 thermometer: 70+ = too hot (overbought), 30- = too cold
  (oversold).
- **Stop loss** — the price where you promise to walk away (the robot picks it).
- **R:R (reward:risk)** — "If I can lose 1 and make 2-3, that's a good deal."
- **Value dip** — a good company that dropped for a dumb reason. Buy the dip,
  responsibly.
- **Benchmark** — the goalpost the robots compare against (usually SPY).

---

## 10. Your first 5-minute tour 🚀

```bash
# 1) make the website appear
cd /d/Users/vince/PycharmProjects/TradingNew/trading_web
py -3.12 -m backend.main

# 2) open http://127.0.0.1:8000 and log in

# 3) Run batch for one ticker, e.g. AAPL
# 4) When done, click Reports -> open the newest folder -> 5_portfolio/decision.md
# 5) Read the FINAL grade + risk gate. Done! 🎉
```

That's the whole loop: **screen → analyze → debate → grade → guard.**

Go explore. If a robot says "unavailable", it means "no data, don't guess" —
and now you know why. 📈