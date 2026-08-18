# Risk Management Plan — risk governor, not risk chatter

Context: the project's risk function is a chatty 3-LLM debate (aggressive/
conservative/neutral + judge). Real firms run a separate, deterministic,
pre-trade control function with limits, stress, escalation and audit; the
LLM only argues at breaches, with numbers. We already compute the math
(contract, ATR stops, CVaR, flow, caps) - this plan makes it enforced.

Sources: FINRS (arXiv 2511.12599), StockBench (2510.02209), Risk-aware
trading RL (2503.04662), coherent risk measures (math/0605062).

## R0 - RiskGovernor (core, deterministic gate)
- strategies/risk_governor.py: limits registry + govern(decision, contract,
  book, cfg) -> {verdict: PASS|WARN|REJECT, reasons[], numbers}
- graph: run after PM/contract; attach risk_gate; only WARN/REJECT go to the
  LLM risk team (kills chatter); risk_halt flag on REJECT.

## R1 - Terse risk reporting
- build_risk_snapshot(verdict, contract) -> compact numbers table text
- structured RiskVerdict (agree/warn/reject + reasons) for the debate
- max_risk_discuss_rounds=1 in snapshot mode

## R2 - Book & tail risk
- strategies/book_risk.py: daily VaR/CVaR (reuse cvar_budget), stress shocks
  (-10% / -30%), drawdown governor
- scripts/risk_report.py

## R3 - Escalation & kill switch
- two-person rule: PM override on REJECT requires escalation note
- risk_halt flag + halt list; paper-trade default stays

## R4 - Audit & measure
- risk_audit.jsonl (verdicts, limits hit, book state)
- reflection ledger gains risk verdict tags; `enable_threshold_gate` guards
  any tuned limit.

Config keys (default in code False; .env true): enable_risk_governor,
risk_max_drawdown_pct 0.10, risk_daily_cvar_budget_pct 0.03,
risk_stress_shock_pct_1 -10, risk_stress_shock_pct_2 -30,
risk_max_position_pct 0.45 (book cap), risk_audit_enabled true.

Sequencing: R0 module+tests -> graph hook -> regression -> R1 -> R2 ->
R3 -> R4; each unit-tested with timers, full regression timed, README/CHANGELOG,
commit/push.