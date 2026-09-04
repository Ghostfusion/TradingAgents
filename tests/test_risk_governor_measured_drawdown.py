"""Regression: the governor's drawdown stop must use the *measured* book
drawdown, not the config limit passed to itself.

Found in LULU (2026-09-04, interactive CLI): the market analyst measured book
drawdown 25.58% -> drawdown_gate=True (BLOCKED), yet the final "Risk Gate
(computed)" said PASS. Root cause: ``trading_graph`` fed
``drawdown_pct=self.config.get("risk_max_drawdown_pct")`` into ``govern``,
so the check ``limit > limit`` was always False - the R0/R2 realized-
drawdown stop could never fire. Fix: resolve the measured basket drawdown
(``_basket_drawdown`` -> ``book_risk.portfolio_drawdown``) and feed that.

Hermetic: vendor chain is monkeypatched with synthetic closes; no network.
"""

from tradingagents.default_config import DEFAULT_CONFIG
from tradingagents.graph.trading_graph import TradingAgentsGraph
from tradingagents.strategies.book_risk import portfolio_drawdown
from tradingagents.strategies.risk_governor import govern


def _closes_climb_then_crash(n_up: int = 10, n_down: int = 7) -> list[float]:
    """Synthetic closes: +1%/day then -5%/day (a ~30% peak-to-trough)."""
    closes = [100.0]
    for _ in range(n_up):
        closes.append(closes[-1] * 1.01)
    for _ in range(n_down):
        closes.append(closes[-1] * 0.95)
    return closes


def test_portfolio_drawdown_measured_not_limit():
    """The pure helper returns the measured magnitude (>> the 10% limit)."""
    closes = _closes_climb_then_crash()
    rets = [closes[i] / closes[i - 1] - 1.0 for i in range(1, len(closes))]
    dd = portfolio_drawdown({"a": 0.5, "b": 0.5}, {"a": rets, "b": rets})
    assert dd is not None and dd > 0.25 and dd < 0.40


def test_graph_basket_drawdown_is_measured(monkeypatch):
    """The graph helper resolves the measured book drawdown (not the limit)."""
    cfg = dict(DEFAULT_CONFIG)
    cfg.update({
        "risk_basket_tickers": ["A", "B"],
        "risk_basket_weights": {"A": 0.6, "B": 0.4},
        "risk_max_drawdown_pct": 0.10,  # the limit, which must NOT be returned
    })
    ta = TradingAgentsGraph(debug=False, config=cfg)
    closes = _closes_climb_then_crash()
    ta._try_fetch_closes = lambda ticker, days=320: list(closes)  # vendor chain mocked
    dd = ta._basket_drawdown("A")
    assert dd is not None
    assert dd > 0.25  # measured crash, far past the 0.10 limit
    assert dd != cfg["risk_max_drawdown_pct"]


def test_govern_rejects_on_measured_drawdown():
    """govern with the measured drawdown past the limit -> REJECT + reason."""
    v = govern(0.05, {"risk_max_drawdown_pct": 0.10}, drawdown_pct=0.256)
    assert v["verdict"] == "REJECT"
    assert any("drawdown" in r for r in v["reasons"])


def test_govern_passes_when_measured_under_limit():
    v = govern(0.05, {"risk_max_drawdown_pct": 0.10}, drawdown_pct=0.05)
    assert v["verdict"] == "PASS"
