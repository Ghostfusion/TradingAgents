"""Moomoo period-order + prior-period canonicalisation (was: stale latest).

Regression tests for the value_screener canonical pipeline:

1. moomoo statements list periods newest-first; the old last-write-wins dict
   kept the OLDEST period's values. The canonical latest must be the NEWEST.
2. Canonical items now carry ``{current, prior}`` dicts for keys present in
   two consecutive periods, so the Beneish M-Score (which needs prior
   values) actually computes instead of returning n/a.
3. moomoo ``-``-prefixed sub-item / contra lines must be skipped, and the
   ``d&a`` alias must not substring-match ``and admin``.
"""

import pytest

import scripts.value_screener as vs
from tradingagents.dataflows.quantitative_scores import beneish_m_score

INCOME_TWO = """## Income Statement — US.MT

### 2025/FY  (FY 2025, currency: USD)
| Item | Value | YoY | QoQ |
| --- | --- | --- | --- |
| Total Revenue | $61.35B | -1.74% | -- |
| Cost of Revenue | $56.98B | 0.57% | -- |
| Selling and Admin Expenses | $2.61B | 5.17% | -- |
| Operating Profit | $1.46B | -52.99% | -- |
| Net Income | $3.15B | -- | -- |

### 2024/FY  (FY 2024, currency: USD)
| Item | Value | YoY | QoQ |
| --- | --- | --- | --- |
| Total Revenue | $62.44B | -- | -- |
| Cost of Revenue | $56.65B | -- | -- |
| Selling and Admin Expenses | $2.48B | -- | -- |
| Operating Profit | $2.30B | -- | -- |
| Net Income | $1.34B | -- | -- |
"""

BALANCE_TWO = """## Balance Sheet — US.MT

### 2025/FY  (FY 2025, currency: USD)
| Item | Value | YoY | QoQ |
| --- | --- | --- | --- |
| Total Current Assets | $30.61B | -- | -- |
| Receivables | $5.94B | -- | -- |
| -Accounts Receivable | $3.48B | -- | -- |
| Net PPE | $41.04B | -- | -- |
| -Accumulated Depreciation | $-31.33B | -- | -- |
| Financial Assets | $5.39B | -- | -- |
| Total Assets | $97.70B | -- | -- |
| Total Current Liabilities | $22.52B | -- | -- |
| Long Term Debt and Capital Lease Obligation | $10.67B | -- | -- |
| Total Equity | $56.54B | -- | -- |

### 2024/FY  (FY 2024, currency: USD)
| Item | Value | YoY | QoQ |
| --- | --- | --- | --- |
| Total Current Assets | $29.38B | -- | -- |
| Receivables | $5.66B | -- | -- |
| Net PPE | $33.31B | -- | -- |
| Financial Assets | $6.40B | -- | -- |
| Total Assets | $89.39B | -- | -- |
| Total Current Liabilities | $21.82B | -- | -- |
| Long Term Debt and Capital Lease Obligation | $8.81B | -- | -- |
| Total Equity | $43.40B | -- | -- |
"""

CASHFLOW_TWO = """## Cash Flow — US.MT

### 2025/FY  (FY 2025, currency: USD)
| Item | Value | YoY | QoQ |
| --- | --- | --- | --- |
| Operating Cash Flow | $4.81B | -- | -- |
| Depreciation & Depletion & Amortization | $2.94B | -- | -- |

### 2024/FY  (FY 2024, currency: USD)
| Item | Value | YoY | QoQ |
| --- | --- | --- | --- |
| Operating Cash Flow | $4.85B | -- | -- |
| Depreciation & Depletion & Amortization | $2.63B | -- | -- |
"""


def _build_canon():
    fin = {}
    for payload in (INCOME_TWO, BALANCE_TWO, CASHFLOW_TWO):
        fin.update(vs._canonicalize(payload))
    fin["market_cap"] = 47.7e9  # mirror mover-meta injection
    return fin


def test_newest_period_wins_not_oldest():
    """Revenue must be 2025 (61.35B), not the oldest period a last-write-wins
    dict would have kept."""
    fin = _build_canon()
    assert vs._latest(fin["revenue"]) == pytest.approx(61.35e9)
    assert fin["revenue"]["prior"] == pytest.approx(62.44e9)


def test_revenue_yoy_from_newest_period():
    fin = _build_canon()
    # -1.74% is the 2025 YoY column value.
    assert fin["revenue_yoy"] == pytest.approx(-0.0174)


def test_canonical_prior_dicts_present():
    fin = _build_canon()
    for key in ("revenue", "net_income", "total_assets", "operating_cashflow"):
        v = fin[key]
        assert isinstance(v, dict) and "current" in v and "prior" in v, key


def test_dash_prefix_lines_skipped_aggregate_wins():
    # -Accounts Receivable (3.48B) is a sub-item; the aggregate Receivables
    # (5.94B) must win.
    fin = _build_canon()
    assert vs._latest(fin["net_receivables"]) == pytest.approx(5.94e9)
    # -Accumulated Depreciation (contra, negative) must be skipped; the
    # cashflow Depreciation & Depletion & Amortization (2.94B) wins over sga.
    assert vs._latest(fin["depreciation"]) == pytest.approx(2.94e9)
    assert vs._latest(fin["sga"]) == pytest.approx(2.61e9)


def test_d_and_a_alias_does_not_match_selling_and_admin():
    # The old "d&a" alias normalized to "d a" and substring-matched
    # "Selling and Admin Expenses" ("and admin"), making depreciation == sga.
    fin = _build_canon()
    assert vs._latest(fin["depreciation"]) != vs._latest(fin["sga"])


def test_m_score_now_computes():
    fin = _build_canon()
    m = beneish_m_score(fin)
    assert m is not None
    assert -4.0 < m < 2.0  # plausible Beneish range


def test_screen_ticker_m_populated():
    row = vs.screen_ticker("MT", _build_canon())
    assert row["beneish_m"] is not None
    assert row["f_score"] is not None


def test_period_year_helper():
    assert vs._period_year("2025/FY") == 2025
    assert vs._period_year("2026/Q3") == 2026
    assert vs._period_year("") == -1


def test_concatenated_fundamentals_finds_cashflow_rows():
    # A get_fundamentals payload concatenates income+balance+cashflow (multiple
    # tables per year), so cashflow rows live in later tables.
    payload = "\n".join([BALANCE_TWO, CASHFLOW_TWO, INCOME_TWO])
    fin = vs._canonicalize(payload)
    assert isinstance(fin.get("operating_cashflow"), dict)
    assert vs._latest(fin["operating_cashflow"]) == pytest.approx(4.81e9)
    assert fin["operating_cashflow"]["prior"] == pytest.approx(4.85e9)
